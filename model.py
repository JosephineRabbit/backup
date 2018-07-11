import torch
from data import *
from torch import nn
from torch.nn import init
import torch.nn.functional as F
from torch.autograd import Variable
from config import *


# vgg choice
base = {'dss': [64, 64, 'M', 128, 128, 'M', 256, 256, 256, 'M', 512, 512, 512, 'M', 512, 512, 512, 'M']}
# extend vgg choice --- follow the paper, you can change it
extra = {'dss': [(64, 128, 3, [8, 16, 32, 64]), (128, 128, 3, [4, 8, 16, 32]), (256, 256, 5, [8, 16]),
                 (512, 256, 5, [4, 8]), (512, 512, 5, []), (512, 512, 7, [])]}








# vgg16
def vgg(cfg, i, batch_norm=False):
    layers = []
    in_channels = i
    for v in cfg:
        if v == 'M':
            layers += [nn.MaxPool2d(kernel_size=2, stride=2)]
        else:
            conv2d = nn.Conv2d(in_channels, v, kernel_size=3, padding=1)
            if batch_norm:
                layers += [conv2d, nn.BatchNorm2d(v), nn.ReLU(inplace=True)]
            else:
                layers += [conv2d, nn.ReLU(inplace=True)]
            in_channels = v
    return layers


class FeatLayer_last(nn.Module):
    def __init__(self,in_channel,channel,k):
        super(FeatLayer_last,self).__init__()

        self.main = nn.Sequential(nn.Conv2d(in_channel,channel,k,1,k//2),nn.ReLU(inplace=True),
                                  nn.Conv2d(channel,channel,k,1,k//2),nn.ReLU(inplace=True),
                                  nn.Dropout())

        self.o = nn.Conv2d(channel,1,1,1)

    def forward(self, x):
        y = self.main(x)
        y1 = self.o(y)

        return y,y1



# extend vgg: side outputs
class FeatLayer(nn.Module):
    def __init__(self, in_channel, channel,k):

        super(FeatLayer, self).__init__()
        #print("side out:", "k",k)
        self.conv1 = nn.Sequential(nn.Conv2d(in_channel,channel,k,1,k//2), nn.ReLU(inplace=True))

        self.conv_e = nn.Sequential(nn.Conv2d(1+channel,channel,k,1,k//2), nn.ReLU(inplace=True),nn.Dropout())


        self.o1_s = nn.Conv2d(channel, 1, 1, 1)

        self.o1 =nn.Conv2d(channel, 1, 1, 1)
        self.o2 =  nn.Conv2d(channel, 1, 1, 1)


    def forward(self, x,f_e):
        y = self.conv1(x)
        y_e = self.conv_e(torch.cat([y,f_e],1))
        e_s = self.o1_s(y_e)
        e = self.o1(y_e)



        return (y_e,e_s,e)

class Edge_featlayer_2(nn.Module):
    def __init__(self,in_channel,channel):
        super(Edge_featlayer_2,self).__init__()

        self.conv1 =  nn.Conv2d(in_channel, channel, 1, 1)
        self.conv2 =  nn.Conv2d(in_channel, channel, 1, 1)
        self.merge = nn.Conv2d(2*channel,1,1)

    def forward(self, x1,x2):
         y1 = self.conv1(x1)
         y2 = self.conv2(x2)
         y1 = torch.cat([y1,y2],1)
         y2 = self.merge(y1)

         return y2

class Edge_featlayer_3(nn.Module):
    def __init__(self, in_channel, channel):
        super(Edge_featlayer_3, self).__init__()

        self.conv1 = nn.Conv2d(in_channel, channel, 1, 1)
        self.conv2 = nn.Conv2d(in_channel, channel, 1, 1)
        self.conv3 = nn.Conv2d(in_channel, channel, 1, 1)
        self.merge = nn.Conv2d(3 * channel, 1, 1)

    def forward(self, x1, x2,x3):
        y1 = self.conv1(x1)
        y2 = self.conv2(x2)
        y3 = self.conv3(x3)
        y1 = torch.cat([y1, y2,y3], 1)
        y2 = self.merge(y1)

        return y2

def e_extract_layer():
    e_feat_layers = []
    e_feat_layers+=[Edge_featlayer_2(64,21)]
    e_feat_layers += [Edge_featlayer_2(128, 21)]
    e_feat_layers += [Edge_featlayer_3(256, 21)]
    e_feat_layers += [Edge_featlayer_3(512, 21)]
    e_feat_layers += [Edge_featlayer_3(512, 21)]

    return e_feat_layers

# extra part
def extra_layer(vgg, cfg):
    feat_layers, concat_layers, concat_layers_2, scale = [], [],[], 1

    feat_layers += [FeatLayer(64, 128, 3)]
    feat_layers += [FeatLayer(128, 128, 3)]
    feat_layers += [FeatLayer(256, 256, 5)]
    feat_layers += [FeatLayer(512, 256, 5)]
    feat_layers += [FeatLayer(512,512,5)]
    feat_layers += [FeatLayer_last(512, 512, 7)]





    return vgg, feat_layers

class DeconvBlock(torch.nn.Module):
    def __init__(self, input_size, output_size, kernel_size=4, stride=2, padding=1, batch_norm=False, dropout=False):
        super(DeconvBlock, self).__init__()
        self.deconv = torch.nn.ConvTranspose2d(input_size, output_size, kernel_size, stride, padding)
        self.bn = torch.nn.BatchNorm2d(output_size)
        self.drop = torch.nn.Dropout(0.2)
        self.relu = torch.nn.ReLU(True)
        self.batch_norm = batch_norm
        self.dropout = dropout

    def forward(self, x):
        if self.batch_norm:
            out = self.bn(self.deconv(self.relu(x)))
        else:
            out = self.deconv(self.relu(x))

        if self.dropout:
            return self.drop(out)
        else:
            return out

class D_U(nn.ModuleList):
    def __init__(self):
        super(D_U,self).__init__()
        #self.up = []
        self.up0=DeconvBlock(input_size=512,output_size=256,batch_norm=True)
        self.up1=DeconvBlock(input_size=512, output_size=256, batch_norm=True)
        self.up2=DeconvBlock(input_size=512,output_size=128,batch_norm=True)
        self.up3=DeconvBlock(input_size=256,output_size=128,batch_norm=True)


        self.extract0=nn.ConvTranspose2d(256, 1,  8,8)
        #self.discrim=nn.ConvTranspose2d(256,1,4,4)

        self.extract1 =nn.ConvTranspose2d(256, 1, 4,4)
        self.extract2 = nn.ConvTranspose2d(128, 1, 2, 2)
        self.extract3 =nn.ConvTranspose2d(128, 1,  1, 1)
        self.extract4 = nn.Conv2d(256,1,1,1)

    def forward(self, features):
        mask,e = [],[]
        x = features[4]
        x1 = self.up0(x)
        mask.append(nn.Sigmoid()(self.extract0(x1)))
        #DIC = self.discrim(x1)
        x2 = self.up1(torch.cat([features[3],x1],1))
        e.append(nn.Sigmoid()(self.extract1(x2)))
        x3 = self.up2(torch.cat([features[2],x2],1))
        mask.append(nn.Sigmoid()(self.extract2(x3)))
        x4 = self.up3(torch.cat([features[1],x3],1))
        e.append(nn.Sigmoid()(self.extract3(x4)))
        mask.append(nn.Sigmoid()(self.extract4(torch.cat([features[0],x4],1))))

        return mask,e





# DSS network
class DSS(nn.Module):
    def __init__(self, base, feat_layers, e_feat_layers, nums):
        super(DSS, self).__init__()
        self.extract = [3, 8, 15, 22, 29]
        self.e_extract = [1,3,6,8,11,13,15,18,20,22,25,27,29]
        #print('------connect',connect)

        self.base = nn.ModuleList(base)
        self.feat = nn.ModuleList(feat_layers)
        self.e_feat =nn.ModuleList(e_feat_layers)
        self.up =nn.ModuleList()
        self.up1 = nn.ModuleList()
        self.up2  = nn.ModuleList()
        self.up3 = nn.ModuleList()

        self.fuse =nn.Conv2d(5,1,1,1)
        #self.up.append(nn.Conv2d(1,1,1))

        k = 1.
        for i  in range(5):
            self.up.append(nn.ConvTranspose2d(1, 1, k,k))
            k = 2 * k

        k1 = 1.
        for i in range(6):
            self.up1.append(nn.ConvTranspose2d(1, 1, k1, k1))
            k1 = 2 * k1

        k2 = 1.
        for i in range(5):
            self.up2.append(nn.ConvTranspose2d(1, 1, k2, k2))
            k2 = 2 * k2
        k3 = 1.
        for i in range(6):
            self.up3.append(nn.ConvTranspose2d(1, 1, k3, k3))
            k3 = 2 * k3


        self.pool = nn.AvgPool2d(3, 1, 1)
        self.pool2 =nn.AvgPool2d(3, 1, 1)



    def forward(self, x1,x2):
        #print(self.e_feat)

        xx2,es,eed, ss,xx,edges,y, y1,y2,y3, num =[],[], [], [],[],[],[],[],[],[], 0
        for k in range(len(self.base)):
            #print(k)

            x1 = self.base[k](x1)

            if k in self.e_extract:
                xx.append(x1)
            #edges.append()
            #print(k,x.size())
            if k in self.extract:
                if num<2:

                    edge =self.e_feat[num](xx[2*num],xx[2*num+1])

                else:
                    edge = self.e_feat[num](xx[num*3-2],xx[num*3-1],xx[num*3])


                #edges.append(edge)


                (y_e,e_s,e)=self.feat[num](x1,edge)
                y.append(y_e)
                y1.append(e_s)
                y2.append(e)



                num += 1
        # side output
        #print(len(y3))


        a,b=self.feat[num](self.pool(x1))
        y.append(a)
        y1.append(b)

        num=0
        for k in range(len(self.base)):
            #print(k)

            x2 = self.base[k](x2)

            if k in self.e_extract:
                xx2.append(x2)
            #edges.append()
            #print(k,x.size())
            if k in self.extract:
                if num<2:

                    edge =self.e_feat[num](xx2[2*num],xx2[2*num+1])

                else:
                    edge = self.e_feat[num](xx2[num*3-2],xx2[num*3-1],xx2[num*3])


                edges.append(edge)
                num+=1


        for i in range(5):
            edges[i] = self.up[i](edges[i])


            es.append(self.up1[i](y1[i]))
            es[i] = nn.Sigmoid()(es[i])

            eed.append(self.up2[i](y2[i]))
            eed[i] = nn.Sigmoid()(eed[i])



        e_f = torch.cat([edges[0], edges[1], edges[2], edges[3], edges[4]], 1)
        edges.append(self.fuse(e_f))

        for i in range(6):
            edges[i]=nn.Sigmoid()(edges[i])

        es.append(self.up1[5](y1[5]))
        es[5]=nn.Sigmoid()(es[5])

            #print(i)




        return (y,edges,es,eed)






def initialize_weights(net):
    for m in net.modules():
        if isinstance(m, nn.Conv2d):
            m.weight.data.normal_(0, 0.05)
            m.bias.data.zero_()
        elif isinstance(m, nn.ConvTranspose2d):
            m.weight.data.normal_(0, 0.05)
            m.bias.data.zero_()
        elif isinstance(m, nn.Linear):
            m.weight.data.normal_(0, 0.05)
            m.bias.data.zero_()


class DSE(nn.Module):
    def __init__(self):
        super(DSE, self).__init__()
        self.net = DSS(*extra_layer(vgg(base['dss'], 3), extra['dss']),e_extract_layer(),nums =BATCH_SIZE)

    def forward(self, input1,input2):
        x = self.net(input1,input2)
        return x




if __name__ == '__main__':
    net = DSE()
    net.train()
    net.cuda()


    net2 = D_U().cuda()


    x = Variable(torch.rand(1,3,256,256)).cuda()
    x2 = Variable(torch.rand(1,3,256,256)).cuda()
    (out,edges,e_s,e) = net(x,x2)


    m,e = net2(out)

    for i in e:
        print(i.shape)
    #print(net.net.base)
    #print(len(e))


    #print(out[0].size())
    #print(len(out))

