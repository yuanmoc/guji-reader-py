from core.utils.logger import info, error

class OcrDataUtil:
    """
    OCR数据处理工具类。
    提供方向检测、区域过滤、排序等OCR后处理功能，便于古籍PDF的结构化文本提取。
    """
    def detect_text_orientation(self, ocr_data):
        """
        判断文字方向是横向还是竖向。
        :param ocr_data: dict，包含OCR识别结果（需含'rec_polys'）
        :return: str，'horizontal' 或 'vertical'
        """
        polys = ocr_data["rec_polys"]
        if not polys:  # 空数据直接返回默认值
            info("OCR方向检测: 空数据，默认horizontal")
            return "horizontal"

        # 1. 计算每个文本行的边界框和宽高比
        boxes = []
        aspects = []
        for poly in polys:
            xs = [p[0] for p in poly]
            ys = [p[1] for p in poly]
            x_min, x_max = min(xs), max(xs)
            y_min, y_max = min(ys), max(ys)

            w, h = x_max - x_min, y_max - y_min
            boxes.append((x_min, y_min, x_max, y_max, w, h))
            aspects.append(w / h if h > 0 else 10)  # 防除零处理

        # 2. 统计主流方向 (采用少数服从多数原则)
        vertical_lines = 0
        horizontal_lines = 0

        for i, (box, ar) in enumerate(zip(boxes, aspects)):
            # 方向判断基准：仅依据宽高比
            if ar < 0.6:
                vertical_lines += 1
            elif ar > 1.4:
                horizontal_lines += 1
            # 中间态宽高比(0.6-1.4)不作计数

        # 3. 少数服从多数决策
        if vertical_lines > horizontal_lines:
            info("OCR方向检测: 判定为vertical")
            return "vertical"
        elif horizontal_lines > vertical_lines:
            info("OCR方向检测: 判定为horizontal")
            return "horizontal"

        # 4. 平局时使用全局特征判断
        all_x = [x for box in boxes for x in (box[0], box[2])]
        all_y = [y for box in boxes for y in (box[1], box[3])]

        global_w = max(all_x) - min(all_x)
        global_h = max(all_y) - min(all_y)
        global_ar = global_w / global_h if global_h > 0 else 1
        info(f"OCR方向检测: 平局，使用全局特征global_ar={global_ar}")
        # vertical 竖向
        return "vertical" if global_ar < 0.8 else "horizontal"

    def filter_by_orientation(self, orientation, ocr_data):
        """
        根据整体文本方向过滤文字区域。
        规则：
        - 如果整体为竖版文字，删除所有横向文本区域
        - 如果整体为横向文字，删除所有竖向文本区域
        :param orientation: 'vertical' 或 'horizontal'
        :param ocr_data: dict，包含OCR识别结果
        :return: dict，过滤后的文本数据
        """
        polys = ocr_data["rec_polys"]
        texts = ocr_data["rec_texts"]
        scores = ocr_data["rec_scores"]

        filtered_texts = []
        filtered_scores = []
        filtered_polys = []

        # 如果没有文本行，直接返回
        if not polys:
            info("OCR方向过滤: 无文本行，直接返回空")
            return {
                "rec_texts": filtered_texts,
                "rec_scores": filtered_scores,
                "rec_polys": filtered_polys
            }

        # 2. 计算每个文本行的宽高比和方向特征
        for i, poly in enumerate(polys):
            xs = [p[0] for p in poly]
            ys = [p[1] for p in poly]
            x_min, x_max = min(xs), max(xs)
            y_min, y_max = min(ys), max(ys)

            w, h = x_max - x_min, y_max - y_min
            aspect_ratio = w / h if h > 0 else 10

            # 3. 判断该文本行是否符合整体方向
            keep = True
            if orientation == "vertical":
                # 竖版文本：删除宽高比>0.6的横向文本行
                if aspect_ratio > 1.5:
                    keep = False
                    info(f"OCR竖方向过滤: 行{i}被过滤，宽高比例{aspect_ratio}, {texts[i]}")
            else:  # horizontal
                # 横向文本：删除宽高比<1.4的竖向文本行
                if aspect_ratio < 1.5:
                    keep = False
                    info(f"OCR横方向过滤: 行{i}被过滤，宽高比例{aspect_ratio}, {texts[i]}")

            # 4. 符合方向要求的保留
            if keep:
                filtered_texts.append(texts[i])
                filtered_scores.append(scores[i])
                filtered_polys.append(poly)

        return {
            "orientation": orientation,
            "rec_texts": filtered_texts,
            "rec_scores": filtered_scores,
            "rec_polys": filtered_polys
        }

    def sort_by_orientation(self, ocr_data):
        """
        根据文本方向调整文字顺序，保证阅读顺序正确。
        :param ocr_data: dict，包含OCR识别结果
        :return: dict，排序并过滤后的文本数据
        """
        try:
            info("OCR数据排序处理开始")
            polys = ocr_data["rec_polys"]
            texts = ocr_data["rec_texts"]
            scores = ocr_data["rec_scores"]

            # 1. 检测文本方向
            orientation = self.detect_text_orientation(ocr_data)

            # 2. 提取边界框特征
            boxes = []
            for poly in polys:
                xs = [p[0] for p in poly]
                ys = [p[1] for p in poly]
                boxes.append((min(xs), min(ys), max(xs), max(ys)))

            # 3. 按方向排序
            if orientation == "horizontal":
                # 横向排序：从上到下，从左到右
                sorted_indices = sorted(range(len(boxes)),
                                        key=lambda i: (boxes[i][1], boxes[i][0]))
            else:
                # 竖版排序：从右到左，从上到下
                # 改进的竖版排序：考虑列布局
                # 获取全局X范围用于确定列分组阈值
                all_x = [x for box in boxes for x in (box[0], box[2])]
                if not all_x:
                    sorted_indices = list(range(len(boxes)))
                else:
                    min_x, max_x = min(all_x), max(all_x)
                    # 计算列分组阈值（全局宽度的5%）
                    threshold = max(10, 0.05 * (max_x - min_x))

                    # 创建按列分组的字典
                    col_dict = {}
                    col_keys = []  # 用于保持列顺序

                    for idx, box in enumerate(boxes):
                        x_center = (box[0] + box[2]) / 2

                        # 查找最接近的已有列
                        matched = False
                        for col_key in col_dict.keys():
                            if abs(x_center - col_key) <= threshold:
                                col_dict[col_key].append((idx, box))
                                matched = True
                                break

                        if not matched:
                            col_dict[x_center] = [(idx, box)]
                            col_keys.append(x_center)

                    # 对每列内的文本行从上到下排序
                    for col_x in col_keys:
                        col_dict[col_x] = sorted(col_dict[col_x],
                                                 key=lambda item: item[1][1])

                    # 对所有列按X坐标从右到左排序（降序）
                    col_keys_sorted = sorted(col_keys, reverse=True)

                    # 构建最终的排序索引
                    sorted_indices = []
                    for col_x in col_keys_sorted:
                        sorted_indices.extend([item[0] for item in col_dict[col_x]])

            # 4. 按排序索引重组所有数据
            sorted_texts = [texts[i] for i in sorted_indices]
            sorted_scores = [scores[i] for i in sorted_indices]
            sorted_polys = [polys[i] for i in sorted_indices]

            # 返回排序后的完整数据结构
            handler_ocr_data = {
                "orientation": orientation,
                "rec_texts": sorted_texts,
                "rec_scores": sorted_scores,
                "rec_polys": sorted_polys
            }

            # 过滤
            return self.filter_by_orientation(orientation, handler_ocr_data)
        except Exception as e:
            error(f"OCR数据排序处理异常: {e}")
            return ocr_data