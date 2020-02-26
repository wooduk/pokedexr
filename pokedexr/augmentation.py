# AUTOGENERATED! DO NOT EDIT! File to edit: nbs/02_augmentation.ipynb (unless otherwise specified).

__all__ = ['augment_brightness_camera_images', 'transform_image', 'fetch_background_images', 'BKG_SRC',
           'apply_random_background']

# Cell

import cv2

def augment_brightness_camera_images(image,brightness):
    image1 = cv2.cvtColor(image,cv2.COLOR_RGB2HSV)
    # I modified this to suit my needs
    random_bright = brightness+np.random.uniform(low=0.0, high=1-brightness)
    image1[:,:,2] = image1[:,:,2]*random_bright
    image1 = cv2.cvtColor(image1,cv2.COLOR_HSV2RGB)
    return image1

def transform_image(img,ang_range,shear_range,trans_range,brightness=0):
    '''
    This function transforms images to generate new images.
    The function takes in following arguments,
    1- Image
    2- ang_range: Range of angles for rotation
    3- shear_range: Range of values to apply affine transform to
    4- trans_range: Range of values to apply translations over.

    A Random uniform distribution is used to generate different parameters for transformation

    '''

    # zoom
    height, width, channels = img.shape

    #prepare the crop
    scale=np.random.uniform(low=0.7, high=1.3)

    centerX,centerY=int(height/2),int(width/2)
    radiusX,radiusY= int(np.round(scale*height/2)),int(np.round(scale*width/2))

    minX,maxX=centerX-radiusX,centerX+radiusX
    minY,maxY=centerY-radiusY,centerY+radiusY

    if scale > 1:
        # zoom out
        new_image = np.zeros(((maxX-minX)+1, (maxY-minY)+1,3),dtype=np.uint8)
        x0=-1*minX; y0=-1*minY
        new_image[y0:y0+height,x0:x0+width,:]=img
        img=new_image.copy()

    else:
        cropped = img[minX:maxX, minY:maxY]
        resized_cropped = cv2.resize(cropped, (width, height))
        img=resized_cropped

    # Rotation

    ang_rot = np.random.uniform(ang_range)-ang_range/2
    rows,cols,ch = img.shape
    Rot_M = cv2.getRotationMatrix2D((cols/2,rows/2),ang_rot,1)

    # Translation
    tr_x = trans_range*np.random.uniform()-trans_range/2
    tr_y = trans_range*np.random.uniform()-trans_range/2
    Trans_M = np.float32([[1,0,tr_x],[0,1,tr_y]])

    # Shear
    pts1 = np.float32([[5,5],[20,5],[5,20]])

    pt1 = 5+shear_range*np.random.uniform()-shear_range/2
    pt2 = 20+shear_range*np.random.uniform()-shear_range/2

    # Brightness


    pts2 = np.float32([[pt1,5],[pt2,pt1],[5,pt2]])

    shear_M = cv2.getAffineTransform(pts1,pts2)

    img = cv2.warpAffine(img,Rot_M,(cols,rows))
    img = cv2.warpAffine(img,Trans_M,(cols,rows))
    img = cv2.warpAffine(img,shear_M,(cols,rows))

    if brightness != 0:
      img = augment_brightness_camera_images(img,brightness)

    return img

# Cell
BKG_SRC = 'https://pokedexproject.s3.eu-west-2.amazonaws.com/background_images/'

def fetch_background_images(src=BKG_SRC, n_images=15):

    background_images=[]

    for i in range(1, n_images+1):
        r=requests.get(src+f'back{i}.jpg')
        d=plt.imread(BytesIO(r.content),0)
        background_images.append(d)

    return background_images


# Cell
def apply_random_background(img,background_images):
    """
    simple image compositor
    select random background image from the set provided
    img : target image (numpy array)
    background_images: list of images (numpy array) as backgrounds
    """
    img1 = img.copy()
    N = len(background_images)
    i = int(np.clip(np.round((N-1)*np.random.uniform()),0,N-1))
    img2=np.array(Image.fromarray(background_images[i]).resize(Image.fromarray(img).size))

    # create mask for empty areas of target image
    idx=(img<5)

    # copy background into those empty areas
    print(img2.shape,img.shape)
    img1[idx]=img2[idx]

    return img1