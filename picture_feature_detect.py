import ssl
import pickle
import logging
from enum import Enum
import matplotlib.pyplot as plt

from skimage.color import rgb2gray
from skimage.feature import hog, local_binary_pattern, ORB, match_descriptors, plot_matches
from skimage import exposure
from skimage.transform import resize
import numpy as np

from skimage.io import imread

ssl._create_default_https_context = ssl._create_unverified_context

ROOT = "/Users/liangyue/Documents/frozen_model_vgg_16/"
ORIGINAL_DATA_PATH = ROOT + "url_file/"
FEATURE_PATH = ORIGINAL_DATA_PATH + "feature_results/"
RESULT_PATH = ROOT + "vector_package/"

logging.basicConfig(level=logging.INFO, format='%(name)s - %(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def look_hog_picture(img_path, is_resize: bool=True):
    image = imread(img_path, plugin='pil')
    if is_resize:
        image = resize(image, (224, 224), preserve_range=True, anti_aliasing=False, clip=False)
    fd, hog_image = hog(image, orientations=9, pixels_per_cell=(16, 16),
                        cells_per_block=(3, 3), visualize=True, multichannel=True)
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(8, 4), sharex=True, sharey=True)

    ax1.axis('off')
    ax1.imshow(image, cmap=plt.cm.gray)
    ax1.set_title('Input image')

    hog_image_rescaled = exposure.rescale_intensity(hog_image, in_range=(0, 10))

    ax2.axis('off')
    ax2.imshow(hog_image_rescaled, cmap=plt.cm.gray)
    ax2.set_title('Histogram of Oriented Gradients')
    plt.show()
    return fd


def look_two_picture_match(file1, file2):
    dif = DetectImageFeature()
    img1 = rgb2gray(dif.load_img(file1))
    img2 = rgb2gray(dif.load_img(file2))

    descriptor_extractor = ORB(n_keypoints=200)

    descriptor_extractor.detect_and_extract(img1)
    keypoints1 = descriptor_extractor.keypoints
    descriptors1 = descriptor_extractor.descriptors

    descriptor_extractor.detect_and_extract(img2)
    keypoints2 = descriptor_extractor.keypoints
    descriptors2 = descriptor_extractor.descriptors

    matches12 = match_descriptors(descriptors1, descriptors2, cross_check=True)
    print(matches12.shape)

    fig, ax = plt.subplots(nrows=1, ncols=1)

    plt.gray()

    plot_matches(ax, img1, img2, keypoints1, keypoints2, matches12)
    ax.axis('off')
    ax.set_title("Original Image vs. Transformed Image")

    plt.show()


class DetectMethod(Enum):
    HOG = 1
    LBP = 2
    ORB = 3


class DetectImageFeature(object):
    def __init__(self, is_resize: bool=True, resize_shape: tuple=(224, 224)):
        self.is_resize = is_resize
        self.resize_shape = resize_shape

    def load_img(self, img_path):
        image = imread(img_path, plugin='pil')
        if self.is_resize:
            image = resize(image, self.resize_shape, preserve_range=True, anti_aliasing=False, clip=False)
        return image

    def detect_hog_feature(self, img_path):
        image = self.load_img(img_path)

        fd, hog_image = hog(image, orientations=9, pixels_per_cell=(16, 16),
                            cells_per_block=(3, 3), visualize=True, multichannel=True)
        return fd

    def detect_orb_feature(self, img_path):
        image = self.load_img(img_path)
        image = rgb2gray(image)
        descriptor_extractor = ORB(n_keypoints=200)

        descriptor_extractor.detect_and_extract(image)
        descriptors1 = descriptor_extractor.descriptors
        descriptors = (descriptors1 * 1).reshape(1, 200 * 256)[0]
        return descriptors

    def detect_lbp_feature(self, img_path):
        image = self.load_img(img_path)
        image = rgb2gray(image)
        radius = 3
        n_points = 8 * radius
        lbp = local_binary_pattern(image, n_points, radius, 'uniform')
        n_bins = int(lbp.max() + 1)
        hist, _ = np.histogram(lbp, density=True, bins=n_bins, range=(0, n_bins))
        return hist


def write_vector_to_csv(method: Enum):
    with open(ORIGINAL_DATA_PATH + "post_url_dict.p", "rb") as p:
        cate_img_url_dict = pickle.load(p)

    detect_feature = DetectImageFeature()

    refs = {
        DetectMethod.HOG.name: detect_feature.detect_hog_feature,
        DetectMethod.LBP.name: detect_feature.detect_lbp_feature,
        DetectMethod.ORB.name: detect_feature.detect_orb_feature
    }
    try:
        detect_method = refs[method.name]
    except KeyError as _:
        logger.info(f"Do not support {method.name} method")
        return

    count = 0
    feature_dict = {}
    for post_id, url in cate_img_url_dict.items():
        # 这类链接拿不到图品，为了提高速度过滤掉
        if url.startswith('https://scontent') or url.endswith(".gif"):
            continue
        try:
            feature = detect_method(url)
            feature_dict[post_id] = feature
            count += 1
        except Exception as e:
            logger.info(post_id, url, e)
        if count % 100 == 0:
            logger.info(f"detect {count} post features. ")
        if count > 1000:
            break

    with open(FEATURE_PATH+method.name+"feature.p", "wb") as f:
        pickle.dump(feature_dict, f)


img_file = "https://wx1.sinaimg.cn/orj1080/53db7999gy1gd0cxmhljwj215o0rs4qp.jpg"
img_file2 = "./tfrecord/resize.jpg"
img_file3 = "./test_data/puzzle.jpeg"


def test_distance():
    detect_feature = DetectImageFeature()
    fd1 = detect_feature.detect_orb_feature(img_file)
    fd2 = detect_feature.detect_orb_feature(img_file2)
    fd3 = detect_feature.detect_orb_feature(img_file3)
    all = np.array(np.matrix([fd1.tolist(), fd2.tolist(), fd3]))
    print(all.shape)
    print(np.corrcoef(all))

    p = all
    q = np.matrix(fd2)
    print("q: ", q)
    similarity = np.sum((p != q), axis=1).reshape(1, p.shape[0])
    similarity = similarity.tolist()[0]
    ids = np.argsort(similarity)
    print(similarity)
    print(ids)


if __name__ == "__main__":
    # write_vector_to_csv(DetectMethod.ORB)
    # test_distance()
    # look_hog_picture("https://wx2.sinaimg.cn/orj1080/82488d87gy1gctda842b0j22ns3zke84.jpg")
    look_two_picture_match(
        "https://wx3.sinaimg.cn/orj1080/3dd2a159gy1gbty6fem6lj23402c07wj.jpg",
        "http://mmbiz.qpic.cn/sz_mmbiz_jpg/jTEoOWfUwDNUcXKicvFFtWkJicoo8zx2hxhSBjCy6mIZDqo3T0C385k3zIPPshAD9JYF0QMNLyr3aAStBljOeNzw/0?wx_fmt=jpeg"
    )