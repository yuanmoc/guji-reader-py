from core.utils.logger import info, error
from core.utils.numpy_cconvert import convert_numpy_types


class OcrDataUtil:
    """
    OCR数据处理工具类。
    提供方向检测、区域过滤、排序等OCR后处理功能，便于古籍PDF的结构化文本提取。
    """
    def detect_text_orientation(self, ocr_data):
        """
        判断文字方向是横向还是竖向。
        :param ocr_data: dict，包含OCR识别结果（需含'rec_polys'）
        :return: str，'horizontal' 水平  或 'vertical' 垂直
        """
        polys = ocr_data["rec_polys"]
        if not polys:  # 空数据直接返回默认值
            info("OCR方向检测: 空数据，默认horizontal")
            return "horizontal"

        # 1. 计算每个文本行的边界框和宽高比
        vertical_area = 0
        horizontal_area = 0
        vertical_lines = 0
        horizontal_lines = 0
        for poly in polys:
            xs = [p[0] for p in poly]
            ys = [p[1] for p in poly]
            x_min, x_max = min(xs), max(xs)
            y_min, y_max = min(ys), max(ys)

            w, h = x_max - x_min, y_max - y_min
            ar = w / h if h > 0 else 10  # 防除零处理

            # 新增：面积法判断主导方向（优先级最高）
            # numpy 中的np.array数据长度有限
            area = w * h
            if ar < 0.9:
                vertical_area += area
                vertical_lines += 1
            elif ar > 1.1:
                horizontal_area += area
                horizontal_lines += 1
            # 中间态不计入

        if vertical_area > horizontal_area * 1.05:
            info(f"OCR方向检测: 竖向面积({vertical_area})明显大于横向面积({horizontal_area})，判定为vertical")
            return "vertical"
        elif horizontal_area > vertical_area * 1.05:
            info(f"OCR方向检测: 横向面积({horizontal_area})明显大于竖向面积({vertical_area})，判定为horizontal")
            return "horizontal"

        # 3. 少数服从多数决策
        if vertical_lines > horizontal_lines:
            info("OCR方向检测: 判定为vertical")
            return "vertical"
        else:
            info("OCR方向检测: 判定为horizontal")
            return "horizontal"

    def sort_by_orientation(self, ocr_data):
        """
        根据文本方向调整文字顺序，保证阅读顺序正确。
        :param ocr_data: dict，包含OCR识别结果
        :return: dict，排序并过滤后的文本数据
        """
        try:
            info("OCR数据排序处理开始")
            ocr_data = convert_numpy_types(ocr_data)
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
                # 竖版排序：严格遵循“最右列优先，列内最上优先”
                all_x2 = [box[2] for box in boxes]  # 直接使用所有框的右边界x2（核心修正）
                if not all_x2:
                    sorted_indices = list(range(len(boxes)))
                else:
                    # 1. 阈值计算：基于右边界x2的差异，避免右侧列被合并
                    min_x2, max_x2 = min(all_x2), max(all_x2)
                    box_widths = [box[2] - box[0] for box in boxes]
                    avg_width = sum(box_widths) / len(box_widths) if box_widths else 0
                    # 阈值基于右边界范围和平均宽度，确保右侧列独立性
                    threshold = max(3, 0.02 * (max_x2 - min_x2), 0.2 * avg_width)  # 更严格的阈值

                    # 2. 列分组：基于右边界x2分组（而非x中心），确保右侧列不被合并
                    # 按x2降序排序所有框（先处理最右侧的框，避免被左侧框“吞并”）
                    sorted_boxes = sorted(enumerate(boxes), key=lambda x: x[1][2], reverse=True)
                    cluster_labels = [-1] * len(boxes)
                    current_cluster = 0

                    for idx, (orig_idx, box) in enumerate(sorted_boxes):
                        if cluster_labels[orig_idx] != -1:
                            continue  # 已分组的框跳过
                        # 以当前框的x2为基准，仅合并x2在 [当前x2 - threshold, 当前x2] 范围内的框
                        # 确保只合并当前框左侧（x2更小）且距离近的框，保护右侧框独立性
                        current_x2 = box[2]
                        cluster_labels[orig_idx] = current_cluster
                        # 检查剩余未分组的框（已按x2降序，后续框x2≤当前x2）
                        for j in range(idx + 1, len(sorted_boxes)):
                            j_orig_idx, j_box = sorted_boxes[j]
                            if cluster_labels[j_orig_idx] == -1:
                                if current_x2 - j_box[2] <= threshold:  # 只允许左侧近距离框合并
                                    cluster_labels[j_orig_idx] = current_cluster
                        current_cluster += 1

                    # 构建列字典：键为聚类ID，值为(原始索引, 框)列表
                    col_dict = {}
                    for orig_idx, box in enumerate(boxes):
                        cid = cluster_labels[orig_idx]
                        if cid not in col_dict:
                            col_dict[cid] = []
                        col_dict[cid].append((orig_idx, box))

                    # 3. 列内排序：严格按上边界y1升序（y1越小越靠上，绝对优先）
                    for cid in col_dict:
                        # 仅用y1排序，不引入任何其他因素
                        col_dict[cid].sort(key=lambda item: item[1][1])

                    # 4. 列间排序：严格按列的最大x2降序（x2越大越靠右，绝对优先）
                    # 计算每列的最大x2（列的右边界）
                    col_max_x2 = {
                        cid: max(box[2] for _, box in col_items)
                        for cid, col_items in col_dict.items()
                    }
                    # 仅按最大x2降序排序列，无其他条件
                    sorted_cids = sorted(col_dict.keys(), key=lambda cid: col_max_x2[cid], reverse=True)

                    # 构建最终排序索引
                    sorted_indices = []
                    for cid in sorted_cids:
                        sorted_indices.extend([item[0] for item in col_dict[cid]])

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
            # return self.filter_by_orientation(orientation, handler_ocr_data)
            return handler_ocr_data
        except Exception as e:
            error(f"OCR数据排序处理异常: {e}")
            return ocr_data