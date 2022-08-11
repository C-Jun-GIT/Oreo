import cv2
import os
import base64
import re
from hoshino import Service
from hoshino.typing import MessageSegment

img_path = os.path.join(os.path.dirname(__file__), "Oreo_images/")
img_path = img_path.replace("\\", "/")

sv_help = """
[奥(o)利(re)奥(o)……] 生成奥利奥叠罗汉，后续可以是奥利奥的随意组合
""".strip()

sv = Service(
    name="奥利奥",
    visible=True,
    enable_on_default=True,
    help_=sv_help
)


def init():  # 将加载本地图片作为函数封装起来，以便后续作为模块使用
    imge1 = cv2.imread(img_path + "O.png", cv2.IMREAD_UNCHANGED)  # 上半饼
    imge2_temp = cv2.imread(img_path + "R.png", cv2.IMREAD_UNCHANGED)  # 暂时的馅，后续要做缩小处理
    imge3 = cv2.imread(img_path + "Ob.png", cv2.IMREAD_UNCHANGED)  # 下半饼

    # 空白画布，在最底层为馅的时候要用
    imge_empty = cv2.imread(img_path + "empty.png", cv2.IMREAD_UNCHANGED)

    # 对馅进行处理，缩小到90%，毕竟总不能馅和饼一样大
    scale_percent = 90
    width = int(imge2_temp.shape[1] * scale_percent / 100)
    height = int(imge2_temp.shape[0] * scale_percent / 100)
    imge2 = cv2.resize(imge2_temp, (width, height), interpolation=cv2.INTER_AREA)
    return imge1, imge2, imge3, imge_empty  # 将上半饼，缩小的馅，下半饼以及空白画布作为对象返回


img1, img2, img3, img_empty = init()


#  画布增加（为了让图片能叠加，和ps一个道理）
def png_extend(img, px):
    # 增加有颜色的像素，value的3个值代表RGB，随便啥都行（反正后续要变成透明），这里为白色
    imgb = cv2.copyMakeBorder(
        img, px, 0, 0, 0, cv2.BORDER_CONSTANT, value=[255, 255, 255]
    )
    # 分离4个通道（R，G，B和Alpha（透明度））（虽然平时念RGB比较习惯，不过在opencv里面顺序变成BGR了）
    _, _, _, alpha_channel = cv2.split(imgb)
    alpha_channel[:px, :] = 0  # 把有颜色的像素变透明
    return imgb  # 处理完的画布作为整体返回


def add_t(imgb):  # 增加上半饼，只在要叠加最上面一层的时候使用
    roi = imgb[0:410, 0:600]  # 设置要叠加的区域

    # 下面的步骤为opencv中教科书般的“按位运算”操作，和百度能找到的教程几乎一样
    img1gray = cv2.cvtColor(img1, cv2.COLOR_BGR2GRAY)

    # 这里的第二个参数253不是唯一可用的值，可在255以内随意尝试
    # 不过太低会导致图像识别差异过大，我试过的最低大概是248左右
    _, mask = cv2.threshold(img1gray, 253, 255, cv2.THRESH_BINARY)

    mask_inv = cv2.bitwise_not(mask)
    img4_bg = cv2.bitwise_and(roi, roi, mask=mask)
    img1_fg = cv2.bitwise_and(img1, img1, mask=mask_inv)
    dst = cv2.add(img4_bg, img1_fg)
    imgb[0:410, 0:600] = dst
    return imgb  # 处理完的画布作为整体返回


def add_re(imgb):  # 注释同函数add_t
    roi = imgb[0:369, 30:570]
    regray = cv2.cvtColor(img2, cv2.COLOR_BGR2GRAY)
    _, mask = cv2.threshold(regray, 253, 255, cv2.THRESH_BINARY)
    mask_inv = cv2.bitwise_not(mask)
    imgb_bg = cv2.bitwise_and(roi, roi, mask=mask)
    re_fg = cv2.bitwise_and(img2, img2, mask=mask_inv)
    dst = cv2.add(imgb_bg, re_fg)
    imgb[0:369, 30:570] = dst
    return imgb


def add_b(imgb):  # 注释同函数add_t
    roi = imgb[0:410, 0:600]
    img1gray = cv2.cvtColor(img3, cv2.COLOR_BGR2GRAY)
    _, mask = cv2.threshold(img1gray, 253, 255, cv2.THRESH_BINARY)
    mask_inv = cv2.bitwise_not(mask)
    img4_bg = cv2.bitwise_and(roi, roi, mask=mask)
    img1_fg = cv2.bitwise_and(img3, img3, mask=mask_inv)
    dst = cv2.add(img4_bg, img1_fg)
    imgb[0:410, 0:600] = dst
    return imgb


def image_to_base64(image_cv2):
    image = cv2.imencode(".png", image_cv2)[1]
    image_code = str(base64.b64encode(image))[2:-1]
    return "base64://" + image_code


# @sv.on_prefix("Oreo")
# 改用正则表达式让这个功能更好玩，无需命令前缀，无视大小写
# @sv.on_rex(r"(?i)^((奥|利|o|re)+)?$")
# 下面这个加入了奥=a，利=l（也就是拼音首字母），按需开启，函数内正则表达式已支持识别无需改动
@sv.on_rex(r"(?i)^((奥|利|o|re|a|l)+)?$")
async def draworeo(bot, ev):
    name = ev.message.extract_plain_text().strip()
    if re.match(r"\[CQ:image,file", name):
        print("是图片，结束……")
        return
    # 预处理
    if re.match(r"(?i)[奥o]", name[-1]):
        img4 = img3.copy()
    else:
        img4 = add_re(img_empty.copy())
    # 因为采用单独校验单个字符的原因，输入re的时候会同时尝试识别r和e，所以去除e
    # 实际影响仅在第一二层，因为后续层e是无法完成正则识别的
    # 尽管如此，去除e更简单粗暴
    name = name.replace("e", "")

    # 对除去顶层以外的部分进行叠图（因为顶层有可能要叠上半饼，所以后续拉出来单独处理）
    for i in range(0, len(name) - 2):
        first = name[len(name) - i - 1]
        last = name[len(name) - i - 2]
        if re.match(r"(?i)[奥oa]", first) and re.match(r"(?i)[利rl]", last):
            """底+馅要拓展40像素"""
            imgt = png_extend(img4, 40)
            img4 = add_re(imgt)
        elif re.match(r"(?i)[利rl]", first) and re.match(r"(?i)[利rl]", last):
            """馅+馅要拓展60像素"""
            img4 = png_extend(img4, 60)
            img4 = add_re(img4)
        elif re.match(r"(?i)[利rl]", first) and re.match(r"(?i)[奥oa]", last):
            """馅+底/顶要拓展84像素"""
            img4 = png_extend(img4, 84)
            img4 = add_b(img4)
        elif re.match(r"(?i)[奥oa]", first) and re.match(r"(?i)[奥oa]", last):
            """底+底/顶要拓展64像素"""
            img4 = png_extend(img4, 64)
            img4 = add_b(img4)

    # 对顶层单独处理
    first = name[0]
    last = name[1]
    if re.match(r"(?i)[奥oa]", first) and re.match(r"(?i)[利rl]", last):
        img4 = png_extend(img4, 84)
        img4 = add_t(img4)
    elif re.match(r"(?i)[奥oa]", first) and re.match(r"(?i)[奥oa]", last):
        img4 = png_extend(img4, 64)
        img4 = add_t(img4)
    elif re.match(r"(?i)[利rl]", first) and re.match(r"(?i)[奥oa]", last):
        imgt = png_extend(img4, 40)
        img4 = add_re(imgt)
    elif re.match(r"(?i)[利rl]", first) and re.match(r"(?i)[利rl]", last):
        img4 = png_extend(img4, 60)
        img4 = add_re(img4)

    await bot.send(ev, MessageSegment.image(image_to_base64(img4)))
