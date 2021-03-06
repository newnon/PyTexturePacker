# -*- coding: utf-8 -*-
"""----------------------------------------------------------------------------
Author:
    Huang Quanyong (wo1fSea)
    quanyongh@foxmail.com
Date:
    2016/10/19
Description:
    MaxRectsBinPacker.py
----------------------------------------------------------------------------"""

import os

from .. import Utils
from ..PackerInterface import PackerInterface
from .MaxRects import MaxRects, MAX_RANK

SIZE_SEQUENCE = [2 ** ind for ind in range(32)]


def calculate_area(image_rect_list, inner_padding):
    area = 0
    for image_rect in image_rect_list:
        area += image_rect.area + \
                image_rect.width * inner_padding + \
                image_rect.height * inner_padding + \
                inner_padding ** 2
    return area


def cal_init_size(area, min_width, min_height, max_width, max_height):
    min_short = min(min_width, min_height)
    min_long = max(min_width, min_height)

    max_short = min(max_width, max_height)
    max_long = max(max_width, max_height)

    start_i = -1
    start_j = -1

    for i, l in enumerate(SIZE_SEQUENCE):
        if l >= min_short and start_i == -1:
            start_i = i
        if l >= min_long and start_j == -1:
            start_j = i

    short = -1
    long = -1

    for j in range(start_j, len(SIZE_SEQUENCE)):
        l = SIZE_SEQUENCE[j]
        if (short != -1 and long != -1) or l > max_long:
            break

        for i in range(start_i, j + 1):
            s = SIZE_SEQUENCE[i]
            if (short != -1 and long != -1) or s > max_short:
                break

            if area <= l * s:
                short, long = s, l

    if short == -1 and long == -1:
        return tuple((max_height, max_width))

    if min_width == min_long:
        return tuple((long, short))
    else:
        return tuple((short, long))


class MaxRectsBinPacker(PackerInterface):
    """

    """

    def __init__(self, *args, **kwargs):
        """

        :param args:
        """
        super(MaxRectsBinPacker, self).__init__(*args, **kwargs)

    def pack(self, input_images, output_name, output_path="", path_prefix="", sprites_scale = 1.0):
        """

        :param input_images:
        :param output_name:
        :param output_path:
        :return:
        """

        if isinstance(input_images, (tuple, list)):
            image_rects = Utils.load_images_from_paths(input_images, sprites_scale)
        else:
            image_rects = Utils.load_images_from_dir(input_images, sprites_scale)

        if self.trim_mode:
            for image_rect in image_rects:
                image_rect.trim(self.trim_mode)

        print "Images to pack", len(image_rects)
                
        duplicates = {}
        if self.detect_identical_sprites:
            new_image_rects = []
            import hashlib
            
            for image_rect in image_rects:
                found = False
                data = image_rect.image.tobytes()
                hash = hashlib.md5(data).hexdigest()
                for item in new_image_rects:
                    if item[2] == hash and data == item[1]:
                        found = True
                        if item[0].image_path in duplicates:
                            duplicates[item[0].image_path].append(image_rect)
                        else:
                            duplicates[item[0].image_path] = [image_rect]
                if not found:
                    new_image_rects.append((image_rect, data, hash))
            image_rects = []
            for image_rect in new_image_rects:
                image_rects.append(image_rect[0])
            print "Original count", len(image_rects)   
        
        max_rect_list = self._pack(image_rects)

        output_plist_list = []
        output_image_list = []
        output_names_list = []
        
        assert "%d" in output_name or len(
            max_rect_list) == 1, 'more than one output image, but no "%d" in output_name'

        for i, max_rect in enumerate(max_rect_list):
            file_name = output_name if "%d" not in output_name else output_name % i
            packed_image = max_rect.dump_image(self.bg_color)
            packed_plist = max_rect.dump_plist(os.path.split(file_name + self.texture_format)[1], duplicates, path_prefix)

            output_image_list.append(packed_image)
            output_plist_list.append(packed_plist)
            output_names_list.append(file_name)
            if "%d" not in output_name:
                break

        for i, plist in enumerate(output_plist_list):
            Utils.save_plist(plist, os.path.join(output_path, output_names_list[i] + ".plist"))
        for i, image in enumerate(output_image_list):
            if self.reduce_border_artifacts:
                image = Utils.alpha_bleeding(image)
            Utils.save_image(image, os.path.join(output_path, output_names_list[i] + self.texture_format))

    def _init_max_rects_list(self, image_rect_list):
        min_width, min_height = 0, 0
        for image_rect in image_rect_list:
            if min_width < image_rect.width:
                min_width = image_rect.width
            if min_height < image_rect.height:
                min_height = image_rect.height

        min_width += self.inner_padding
        min_height += self.inner_padding

        if self.enable_rotated:
            if min(min_width, min_height) > min(self.max_width, self.max_height) or \
                            max(min_width, min_height) > max(self.max_width, self.max_height):
                raise ValueError("size of image is larger than max size.")
        else:
            if min_height > self.max_height or min_width > self.max_width:
                raise ValueError("size of image is larger than max size.")

        max_rects_list = []
        area = calculate_area(image_rect_list, self.inner_padding)
        w, h = cal_init_size(area, min_width, min_height, self.max_width, self.max_height)

        max_rects_list.append(MaxRects(w, h, self.max_width, self.max_height,
                                       force_square=self.force_square, border_padding=self.border_padding,
                                       shape_padding=self.shape_padding, inner_padding=self.inner_padding))

        area = area - w * h
        while area > 0:
            w, h = cal_init_size(area, 0, 0, self.max_width, self.max_height)
            area = area - w * h
            max_rects_list.append(MaxRects(w, h, self.max_width, self.max_height,
                                           force_square=self.force_square, border_padding=self.border_padding,
                                           shape_padding=self.shape_padding, inner_padding=self.inner_padding))

        return max_rects_list

    def _pack(self, image_rect_list):
        max_rects_list = self._init_max_rects_list(image_rect_list)

        image_rect_list = sorted(image_rect_list, key=lambda x: max(x.width, x.height), reverse=True)

        for image_rect in image_rect_list:
            best_max_rects = -1
            best_index = -1
            best_rank = MAX_RANK
            best_rotated = False

            for i, max_rect in enumerate(max_rects_list):
                index, rank, rotated = max_rect.find_best_rank(image_rect, self.enable_rotated)

                if rank < best_rank:
                    best_max_rects = i
                    best_rank = rank
                    best_index = index
                    best_rotated = rotated

            if MAX_RANK == best_rank:
                for i, max_rect in enumerate(max_rects_list):
                    while MAX_RANK == best_rank:
                        if max_rect.expand():
                            best_max_rects = i
                            best_index, best_rank, best_rotated = max_rect.find_best_rank(image_rect,
                                                                                          self.enable_rotated)
                        else:
                            break
                    if MAX_RANK != best_rank:
                        break
                if MAX_RANK == best_rank:
                    max_rects_list.append(MaxRects(force_square=self.force_square, border_padding=self.border_padding,
                                                   shape_padding=self.shape_padding, inner_padding=self.inner_padding))
                    best_max_rects = len(max_rects_list) - 1
                    best_index, best_rank, best_rotated = max_rects_list[-1].find_best_rank(image_rect,
                                                                                            self.enable_rotated)
                    while MAX_RANK == best_rank:
                        max_rects_list[-1].expand()
                        best_index, best_rank, best_rotated = max_rects_list[-1].find_best_rank(image_rect,
                                                                                                self.enable_rotated)

            if best_rotated:
                image_rect.rotate()

            max_rects_list[best_max_rects].place_image_rect(best_index, image_rect)

        return max_rects_list
