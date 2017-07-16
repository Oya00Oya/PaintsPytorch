import argparse
import random
import torch.backends.cudnn as cudnn
import torch.optim as optim
import torchvision.utils as vutils
from visdom import Visdom
from models.OnepassModel import *
from data.opData import CreateDataLoader

parser = argparse.ArgumentParser()
parser.add_argument('--datarootC', required=True, help='path to colored dataset')
parser.add_argument('--datarootS', required=True, help='path to sketch dataset')
parser.add_argument('--workers', type=int, help='number of data loading workers', default=4)
parser.add_argument('--batchSize', type=int, default=16, help='input batch size')
parser.add_argument('--imageSize', type=int, default=256, help='the height / width of the input image to network')
parser.add_argument('--cut', type=int, default=1, help='cut backup frequency')
parser.add_argument('--niter', type=int, default=700, help='number of epochs to train for')
parser.add_argument('--normG', type=str, default='instance', help='normalization layer for Gnet')
parser.add_argument('--normD', type=str, default='batch', help='normalization layer for Dnet')
parser.add_argument('--ngf', type=int, default=64)
parser.add_argument('--ndf', type=int, default=64)
parser.add_argument('--lrG', type=float, default=0.0001, help='learning rate, default=0.0001')
parser.add_argument('--lrD', type=float, default=0.0001, help='learning rate, default=0.0001')
parser.add_argument('--beta1', type=float, default=0.5, help='beta1 for adam. default=0.5')
parser.add_argument('--cuda', action='store_true', help='enables cuda')
parser.add_argument('--netG', default='', help="path to netG (to continue training)")
parser.add_argument('--netD', default='', help="path to netD (to continue training)")
parser.add_argument('--outf', default='.', help='folder to output images and model checkpoints')
parser.add_argument('--Diters', type=int, default=5, help='number of D iters per each G iter')
parser.add_argument('--manualSeed', type=int, default=2345, help='random seed to use. Default=1234')
parser.add_argument('--baseGeni', type=int, default=2500, help='start base of pure pair L1 loss')
parser.add_argument('--geni', type=int, default=0, help='continue gen image num')
parser.add_argument('--epoi', type=int, default=0, help='continue epoch num')
parser.add_argument('--env', type=str, default='main', help='visdom env')
# parser.add_argument('--gpW', type=float, default=10, help='gradient penalty weight')

opt = parser.parse_args()
print(opt)

####### regular set up
if torch.cuda.is_available() and not opt.cuda:
    print("WARNING: You have a CUDA device, so you should probably run with --cuda")
gen_iterations = opt.geni
try:
    os.makedirs(opt.outf)
except OSError:
    pass
# random seed setup                                  # !!!!!
print("Random Seed: ", opt.manualSeed)
random.seed(opt.manualSeed)
torch.manual_seed(opt.manualSeed)
if opt.cuda:
    torch.cuda.manual_seed(opt.manualSeed)
cudnn.benchmark = True
####### regular set up end


viz = Visdom(env=opt.env)

imageW = viz.images(
    np.zeros((3, 512, 256)),
    opts=dict(title='fakeHR', caption='fakeHR')
)

dataloader = CreateDataLoader(opt)

netG = def_netG(ngf=opt.ngf, norm=opt.normG)
if opt.netG != '':
    netG.load_state_dict(torch.load(opt.netG))
print(netG)

netD = def_netD(ndf=opt.ndf, norm=opt.normD)
if opt.netD != '':
    netD.load_state_dict(torch.load(opt.netD))
print(netD)

criterion_GAN = GANLoss()
if opt.cuda:
    criterion_GAN = GANLoss(tensor=torch.cuda.FloatTensor)
criterion_L1 = nn.L1Loss()
L2_dist = nn.PairwiseDistance(2)

fixed_sketch = torch.FloatTensor()
fixed_hint = torch.FloatTensor()
one = torch.FloatTensor([1])
mone = one * -1

if opt.cuda:
    netD.cuda()
    netG.cuda()
    fixed_sketch, fixed_hint = fixed_sketch.cuda(), fixed_hint.cuda()
    one, mone = one.cuda(), mone.cuda()
    criterion_GAN.cuda()
    criterion_L1.cuda()
    L2_dist.cuda()

# setup optimizer
optimizerG = optim.Adam(netG.parameters(), lr=opt.lrG, betas=(opt.beta1, 0.9))
optimizerD = optim.Adam(netD.parameters(), lr=opt.lrD, betas=(opt.beta1, 0.9))

flag = 1
flag2 = 1
flag3 = 1

for epoch in range(opt.niter):
    data_iter = iter(dataloader)
    i = 0
    while i < len(dataloader):
        ############################
        # (1) Update D network
        ###########################
        for p in netD.parameters():  # reset requires_grad
            p.requires_grad = True  # they are set to False below in netG update
        for p in netG.parameters():
            p.requires_grad = False  # to avoid computation

        # train the discriminator Diters times
        Diters = opt.Diters

        if gen_iterations < opt.baseGeni:  # L1 stage
            Diters = 0

        j = 0
        while j < Diters and i < len(dataloader):

            j += 1
            netD.zero_grad()

            data = data_iter.next()
            real_cim, real_vim, real_sim = data
            i += 1
            ###############################

            if opt.cuda:
                real_cim, real_vim, real_sim = real_cim.cuda(), real_vim.cuda(), real_sim.cuda()

            # train with fake

            fake_cim = netG(Variable(real_sim, volatile=True), Variable(real_vim, volatile=True)).data
            errD_fake_vec = netD(Variable(torch.cat((fake_cim, real_sim), 1)))
            errD_fake = errD_fake_vec.mean()
            errD_fake.backward(one, retain_graph=True)  # backward on score on real

            errD_real_vec = netD(Variable(torch.cat((real_cim, real_sim), 1)))
            errD_real = errD_real_vec.mean()
            errD_real.backward(mone, retain_graph=True)  # backward on score on real

            errD = errD_real - errD_fake

            # GP term
            dist = L2_dist(Variable(real_cim).view(opt.batchSize, -1), Variable(fake_cim).view(opt.batchSize, -1)).view(
                -1)
            lip_est = (errD_real_vec.view(opt.batchSize, -1).mean(1) - errD_fake_vec.view(opt.batchSize, -1).mean(
                1)).abs() / (dist + 1e-8)

            lip_loss = 10 * ((1.0 - lip_est) ** 2).mean(0)  # ????
            lip_loss.backward(one)
            errD = errD + lip_loss

            optimizerD.step()

        ############################
        # (2) Update G network
        ############################
        if i < len(dataloader):
            for p in netD.parameters():
                p.requires_grad = False  # to avoid computation
            for p in netG.parameters():
                p.requires_grad = True  # to avoid computation
            netG.zero_grad()

            data = data_iter.next()
            real_cim, real_vim, real_sim = data
            i += 1

            if opt.cuda:
                real_cim, real_vim, real_sim = real_cim.cuda(), real_vim.cuda(), real_sim.cuda()

            if flag:  # fix samples
                viz.images(
                    real_cim.mul(0.5).add(0.5).cpu().numpy(),
                    opts=dict(title='target img', caption='original')
                )
                vutils.save_image(real_cim.mul(0.5).add(0.5),
                                  '%s/real_samples.png' % opt.outf)
                viz.images(
                    real_sim.mul(0.5).add(0.5).cpu().numpy(),
                    opts=dict(title='sketch', caption='input sketch')
                )
                vutils.save_image(real_sim.mul(0.5).add(0.5),
                                  '%s/input_samples.png' % opt.outf)
                viz.images(
                    real_vim.mul(0.5).add(0.5).cpu().numpy(),
                    opts=dict(title='hint', caption='alternative hint')
                )
                vutils.save_image(real_vim.mul(0.5).add(0.5),
                                  '%s/alternative_hint.png' % opt.outf)

                fixed_sketch.resize_as_(real_sim).copy_(real_sim)
                fixed_hint.resize_as_(real_vim).copy_(real_vim)

                flag -= 1

            fake = netG(Variable(real_sim), Variable(real_vim))

            if gen_iterations < opt.baseGeni:
                L1loss = criterion_L1(fake, Variable(real_cim))
                L1loss.backward()
                errG = L1loss
            else:
                errG_fake_vec = netD(torch.cat((fake, Variable(real_sim)), 1))  # TODO: what if???
                errG = errG_fake_vec.mean()
                errG.backward(mone, retain_graph=True)

                L1loss = criterion_L1(fake, Variable(real_cim))
                L1loss.backward(retain_graph=True)

            optimizerG.step()

        ############################
        # (3) Report & 100 Batch checkpoint
        ############################
        if gen_iterations < opt.baseGeni:
            if flag2:
                L1window = viz.line(
                    np.array([L1loss.data[0]]), np.array([gen_iterations]),
                    opts=dict(title='L1 loss')
                )
                flag2 -= 1
            viz.line(np.array([L1loss.data[0]]), np.array([gen_iterations]), update='append', win=L1window)

            print('[%d/%d][%d/%d][%d] L1 %f '
                  % (epoch, opt.niter, i, len(dataloader), gen_iterations, L1loss.data[0]))
        else:
            if flag3:
                D1 = viz.line(
                    np.array([errD.data[0]]), np.array([gen_iterations]),
                    opts=dict(title='errD(distance)', caption='total Dloss')
                )
                D2 = viz.line(
                    np.array([lip_loss.data[0]]), np.array([gen_iterations]),
                    opts=dict(title='Gradient penalty', caption='real\'s mistake')
                )
                G1 = viz.line(
                    np.array([-errG.data[0]]), np.array([gen_iterations]),
                    opts=dict(title='Gnet loss', caption='fake\'s mistake')
                )
                flag3 -= 1
            if flag2:
                L1window = viz.line(
                    np.array([L1loss.data[0]]), np.array([gen_iterations]),
                    opts=dict(title='L1 loss')
                )
                flag2 -= 1

            viz.line(np.array([errD.data[0]]), np.array([gen_iterations]), update='append', win=D1)
            viz.line(np.array([lip_loss.data[0]]), np.array([gen_iterations]), update='append', win=D2)
            viz.line(np.array([-errG.data[0]]), np.array([gen_iterations]), update='append', win=G1)
            viz.line(np.array([L1loss.data[0]]), np.array([gen_iterations]), update='append', win=L1window)

            print('[%d/%d][%d/%d][%d] distance: %f err_G: %f GPLoss %f L1 %f'
                  % (epoch, opt.niter, i, len(dataloader), gen_iterations,
                     errD.data[0], -errG.data[0], lip_loss.data[0], L1loss.data[0]))

        if gen_iterations % 100 == 0:
            fake = netG(Variable(fixed_sketch, volatile=True), Variable(fixed_hint, volatile=True))
            viz.images(
                fake.data.mul(0.5).add(0.5).cpu().numpy(),
                win=imageW,
                opts=dict(title='generated result', caption='output')
            )

            vutils.save_image(fake.data.mul(0.5).add(0.5),
                              '%s/fake_samples_gen_iter_%08d.png' % (opt.outf, gen_iterations))

        gen_iterations += 1

    # do checkpointing
    if epoch % opt.cut == 0:
        torch.save(netG.state_dict(), '%s/netG_epoch_%d.pth' % (opt.outf, epoch + opt.epoi))
        torch.save(netD.state_dict(), '%s/netD_epoch_%d.pth' % (opt.outf, epoch + opt.epoi))
