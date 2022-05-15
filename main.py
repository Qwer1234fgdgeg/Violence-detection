import random
import time
import torch
import os
from torch.utils.tensorboard import SummaryWriter
from torch.utils.data import DataLoader
from LoadData import VideoDataset
from Model import R3D_18
from torch import nn
from torch import optim

# train+valid模块
def train_model(model, Dataloader, loss_func, optim, epochs):
    max_precision = 0
    writer = SummaryWriter()
    train_count = 0  # 用于计算runtime_loss和输出图像
    device = model.device
    is_new_model = 0
    val_epoch = 0
    model_path = ''
    local_time_dir = ''
    for epoch in range(epochs):
        print("Epoch:{:}".format(epoch))
        for phase in ["train","valid"]:
            runtime_loss = 0
            precision = 0
            if phase == "train":
                model.train()
                print("Training...")
                print("Learning rate = {}".format(optim.state_dict()['param_groups'][0]['lr']))
            elif phase == "valid" and is_new_model == 1:    # 只有当模型参数被更新的时候才计算valid
                model_path = "models/{:s}/model{:s}.pt".format(local_time_dir,str(val_epoch))
                if os.path.exists(model_path):
                    model_dict = torch.load(model_path,map_location=torch.device(device))
                    model.load_state_dict(model_dict["state_dict"])
                    is_new_model = 0    # 重新将模型置为待更新状态
                else:
                    raise RuntimeError("Can't find \'./model.pt\'")
                model.eval()    # 评估模式
                print("Validating...")
            else:
                break       # 如果模型参数是旧版则就不需要计算测试集了
            data_num = 0
            correct_num = 0
            for data in Dataloader[phase]:
                video, target = data
                data_num += video.size(dim=0)
                target = torch.tensor(target).to(torch.long).to(device)
                # 展示数据
                # VideoDataset.showData(video,[writer])
                # 梯度清零，如果不清零梯度就会叠加
                optim.zero_grad()
                with torch.set_grad_enabled(True if phase == "train" else False):
                    # 计算输出
                    output = model(video)
                    if phase == "train":
                        # 计算损失
                        loss = loss_func(output, target)
                        # 迭代和更新
                        loss.backward()
                        optim.step()
                        train_count += 1
                    runtime_loss += loss
                    if (phase == "train" and train_count % 5 == 0):  # 每5次迭代输出一次平均loss
                        writer.add_scalar("Train/Loss", runtime_loss, train_count )
                        print("runtime_loss={}".format(runtime_loss / 5))
                        runtime_loss = 0
                # 计算精度
                _, preds = torch.max(output, dim=1)
                # 展示正确识别的图片
                VideoDataset.showData(video,[writer],preds,target)

                correct_num += torch.sum(preds == target)
            precision = correct_num / data_num * 100        # 计算一个epoch下来的精度
            print("Precision = {}%".format(precision))
            if precision >= max_precision + 0.03 and phase == "train":  # 找到训练时所有epoch中精度最高的那个模型参数,+0.03是为了使得参数更新有意义
                val_epoch += 1      # 叠加模型更新次数
                max_precision = precision
                state = {
                    "state_dict": model.state_dict(),
                    "optim": optim.state_dict()
                }
                # 每天新建一个文件夹储存model
                local_time = time.localtime()
                local_time_dir = str(local_time[0]) + '.' + str(local_time[1]) \
                                 + '.' + str(local_time[2])
                model_path = os.path.join(os.getcwd(),"models",local_time_dir)
                if not os.path.exists(model_path):
                    os.mkdir(model_path)
                torch.save(state, "models/{:s}/model{:s}.pt".format(local_time_dir,str(val_epoch)))
                is_new_model = 1    # 将模型标志为新版
            writer.add_scalar("{:s}/Precision".format("Train" if phase == "train" else "Valid"), precision, epoch if phase == "train" else val_epoch)  # 制作两张图，一个Train一个Valid
    writer.close()

def inference_model(long_vedio_path, model):
    import cv2
    assert os.path.exists(long_vedio_path), "Vedio path may be wrong!"
    long_vedio = cv2.VideoCapture(long_vedio_path)
    fps = long_vedio.get(cv2.CAP_PROP_FPS)




if __name__ == "__main__":
    # 制作数据集
    root_path = os.path.abspath("RWF-2000")
    batch_size = 8
    dataset = {x: VideoDataset(root_path, video_size=8, phase=x, transform=None) for x in ["train", "valid"]}
    Dataloader = {x: DataLoader(dataset[x], batch_size, shuffle=True) for x in ["train", "valid"]}

    # 制作模型
    model = R3D_18(pretrained=True)     # 使用训练好的参数作为初始化参数
    # 设置需要训练的参数
    '''
    layers_need_to_train    ==  0   --> 训练所有层
                            ==  1   --> 仅训练全连接层
                            ==  2   --> 待更新...
    '''
    layers_need_to_train = 0
    param_need_to_update = []
    print("Params need to learn:")
    if layers_need_to_train == 1:
        for name, param in model.named_parameters():
            if name == "model.fc.weight" or name == "model.fc.bias":
                param.requires_grad = True
                param_need_to_update.append(param)
                print(name)
                continue
            param.requires_grad = False
    elif layers_need_to_train == 2:
        pass
    else:
        for name, param in model.named_parameters():
            param.requires_grad = True
            param_need_to_update.append(param)
            print(name)
        print('\n')
    # 制作损失函数和优化器
    loss_func = nn.CrossEntropyLoss()
    lr = 1e-4
    optim = optim.Adam(param_need_to_update, lr)
    # 取出设备
    device = model.device

    # 开始训练
    # train_model(model,Dataloader,loss_func,optim,epochs=30)

