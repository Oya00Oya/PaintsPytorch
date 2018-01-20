import torch.nn as nn

i2v = nn.Sequential(  # Sequential,
    nn.Conv2d(3, 64, (3, 3), (1, 1), (1, 1)),
    nn.ReLU(),
    nn.MaxPool2d((2, 2), (2, 2), (0, 0), ceil_mode=True),
    nn.Conv2d(64, 128, (3, 3), (1, 1), (1, 1)),
    nn.ReLU(),
    nn.MaxPool2d((2, 2), (2, 2), (0, 0), ceil_mode=True),
    nn.Conv2d(128, 256, (3, 3), (1, 1), (1, 1)),
    nn.ReLU(),
    nn.Conv2d(256, 256, (3, 3), (1, 1), (1, 1)),
    nn.ReLU(),
    nn.MaxPool2d((2, 2), (2, 2), (0, 0), ceil_mode=True),
    nn.Conv2d(256, 512, (3, 3), (1, 1), (1, 1)),
    nn.ReLU(),
    nn.Conv2d(512, 512, (3, 3), (1, 1), (1, 1)),
    nn.ReLU(),
    nn.MaxPool2d((2, 2), (2, 2), (0, 0), ceil_mode=True),
    nn.Conv2d(512, 512, (3, 3), (1, 1), (1, 1)),
    nn.ReLU(),
    nn.Conv2d(512, 512, (3, 3), (1, 1), (1, 1)),
    nn.ReLU(),
    nn.MaxPool2d((2, 2), (2, 2), (0, 0), ceil_mode=True),
    nn.Conv2d(512, 1024, (3, 3), (1, 1), (1, 1)),
    nn.ReLU(),
    nn.Conv2d(1024, 1024, (3, 3), (1, 1), (1, 1)),
    nn.ReLU(),
    nn.Conv2d(1024, 1024, (3, 3), (1, 1), (1, 1)),
    nn.ReLU(),
    nn.Dropout(0.5),
    nn.Conv2d(1024, 1539, (3, 3), (1, 1), (1, 1)),
    nn.AvgPool2d((7, 7), (1, 1), (0, 0), ceil_mode=True),  # AvgPool2d,
)