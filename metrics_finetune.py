import csv
import ssl
import pickle
import urllib.request

import tensorflow as tf

from Constant import LabelName

ssl._create_default_https_context = ssl._create_unverified_context


def precess_img(img_file):
    with tf.Session() as sess:
        set_width, set_height = 224, 224
        if img_file.startswith("https:"):
            req = urllib.request.Request(img_file)
            response = urllib.request.urlopen(req)
            img_raw = response.read()
        else:
            img_raw = tf.gfile.FastGFile(img_file, 'rb').read()
        decode_data = tf.image.decode_jpeg(img_raw, channels=3)
        # resize
        decode_data = tf.image.resize_images(decode_data, [set_width, set_height])
        decode_data = tf.cast(decode_data, tf.uint8)
        img = sess.run(decode_data)
    return img


def predict_labels(is_multi=False):
    def session_predict():
        if is_multi:
            result = run_multi_label(sess, inputs, outputs, sub_img_data, csv_writer, sub_img_ids,
                                     sub_labels, sub_img_url, len(sub_img_ids))
        else:
            result = run_single_label(sess, inputs, outputs, sub_img_data, csv_writer, sub_img_ids,
                                      sub_labels, sub_img_url, len(sub_img_ids))
        return result

    test_df_fn = "/Users/liangyue/PycharmProjects/bi_cron_job/backend/works/social_picture/data/test_data.p"
    with open(test_df_fn, "rb") as p:
        df = pickle.load(p)

    frozen_graph_path = "./outfilel2_0.05_2000/frozen_inference_graph.pb"
    model_graph = tf.Graph()
    with model_graph.as_default():
        od_graph_def = tf.GraphDef()
        with tf.gfile.GFile(frozen_graph_path, 'rb') as fid:
            serialized_graph = fid.read()
            od_graph_def.ParseFromString(serialized_graph)
            tf.import_graph_def(od_graph_def, name='')

    batch_size = 200
    with model_graph.as_default():
        with tf.Session(graph=model_graph) as sess:
            inputs = model_graph.get_tensor_by_name('image_tensor:0')
            # logits  classes
            layer_name = "classes"
            if is_multi:
                layer_name = "multi"
            outputs = model_graph.get_tensor_by_name(layer_name + ':0')
            all_pred = []
            all_label = []
            with open("predict_results.csv", "w", encoding="utf-8") as f:
                csv_writer = csv.writer(f)
                csv_writer.writerow(
                    ["id", "url", "truth_label", "predict_label", "truth_label_name", "predict_label_name"]
                )
                sub_img_data, sub_labels, sub_img_url, sub_img_ids = [], [], [], []
                count = 0
                for index, row in df.iterrows():
                    img_id, img_url, label = row["id"], row["url"], row["label"]
                    try:
                        img = precess_img(img_url)
                    except Exception as e:
                        print(e)
                        print(img_id, img_url, label)
                        continue
                    sub_img_data.append(img)
                    sub_labels.append(label)
                    sub_img_url.append(img_url)
                    sub_img_ids.append(img_id)
                    count += 1
                    if len(sub_img_data) == batch_size:
                        print(f"start process {batch_size} img")
                        sub_pred = session_predict()
                        all_pred += sub_pred
                        all_label += sub_labels
                        sub_img_data, sub_labels, sub_img_url, sub_img_ids = [], [], [], []

                if len(sub_img_data) != 0:
                    sub_pred = session_predict()
                    all_pred += sub_pred
                    all_label += sub_labels
    print(len(all_label), all_label)
    print(len(all_pred), all_pred)
    accuracy = sum(1 for x, y in zip(all_label, all_pred) if x in y) / len(all_pred)
    print(accuracy)


def run_single_label(sess, inputs, outputs, sub_img_data, writer, img_ids, labels, img_urls, length):
    predicted_label = __predict_single_label(sess, inputs, outputs, sub_img_data)
    __write_to_file(writer, img_ids, labels, img_urls, predicted_label, length)
    return predicted_label


def run_multi_label(sess, inputs, outputs, sub_img_data, writer, img_ids, labels, img_urls, length):
    predicted_label = __predict_multi_label(sess, inputs, outputs, sub_img_data)
    __write_multi_label_to_file(writer, img_ids, labels, img_urls, predicted_label, length)
    return predicted_label


def __predict_single_label(sess, inputs, outputs, sub_img_data):
    predicted_label = sess.run(outputs, feed_dict={inputs: sub_img_data})
    predicted_label = predicted_label.tolist()
    return predicted_label


def __predict_multi_label(sess, inputs, outputs, sub_img_data):
    predicted_label = sess.run(outputs, feed_dict={inputs: sub_img_data})
    predicted_label = predicted_label.tolist()
    multi_dict = {}
    for row, label in predicted_label:
        multi_dict.setdefault(row, []).append(label)
    return list(multi_dict.values())


def __write_to_file(writer, img_ids, labels, img_urls, pred_labels, length):
    label_name = LabelName()
    for i in range(length):
        writer.writerow(
            [img_ids[i], img_urls[i], labels[i], pred_labels[i], label_name[labels[i]], label_name[pred_labels[i]]]
        )


def __write_multi_label_to_file(writer, img_ids, labels, img_urls, pred_labels, length):
    label_name = LabelName()
    for i in range(length):
        temp_pred_labels = pred_labels[i]
        temp_pred_labels_name = ','.join(map(lambda x: label_name[x], temp_pred_labels))
        writer.writerow(
            [
                img_ids[i],
                img_urls[i],
                labels[i],
                ','.join(map(str, temp_pred_labels)),
                label_name[labels[i]],
                temp_pred_labels_name
            ]
        )


if __name__ == '__main__':
    predict_labels(True)