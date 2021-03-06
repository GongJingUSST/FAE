from abc import ABCMeta,abstractmethod
import numpy as np
import os
import numbers
import csv
import pandas as pd

from sklearn.model_selection import KFold, StratifiedKFold, LeaveOneOut

from FAE.DataContainer.DataContainer import DataContainer
from FAE.FeatureAnalysis.Classifier import Classifier
from FAE.FeatureAnalysis.FeatureSelector import FeatureSelectPipeline, FeatureSelectByAnalysis, FeatureSelector
from FAE.Func.Metric import EstimateMetirc
from FAE.Visualization.PlotMetricVsFeatureNumber import DrawCurve
from FAE.Visualization.DrawROCList import DrawROCList
from FAE.Func.Visualization import LoadWaitBar

class CrossValidation:
    '''
    CrossValidation is the base class to explore the hpyer-parameters. Now it supported Leave-one-lout (LOO), 10-folder,
    and 5-folders. A classifier must be set before run CV. A training metric and validation metric will be returned.
    If a testing data container was also set, the test metric will be return.
    '''
    def __init__(self):
        self._classifier = Classifier()

    def SetClassifier(self, classifier):
        self._classifier = classifier

    def GetClassifier(self):
        return self._classifier

    def SaveResult(self, info, store_path):
        info = dict(sorted(info.items(), key= lambda item: item[0]))

        write_info = []
        for key in info.keys():
            temp_list = []
            temp_list.append(key)
            if isinstance(info[key], (numbers.Number, str)):
                temp_list.append(info[key])
            else:
                temp_list.extend(info[key])
            write_info.append(temp_list)

        write_info.sort()

        # write_info = [[key].extend(info[key]) for key in info.keys()]
        if os.path.isdir(store_path):
            store_path = os.path.join(store_path, 'result.csv')

        with open(store_path, 'w', newline='') as csvfile:
            writer = csv.writer(csvfile, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
            write_info.sort()
            writer.writerows(write_info)

class CrossValidationLeaveOneOut(CrossValidation):
    def __init__(self):
        super(CrossValidationLeaveOneOut, self).__init__()
        self.__cv = LeaveOneOut()

    def GetCV(self):
        return self.__cv

    def GetName(self):
        return 'LeaveOneOut'

    def GetDescription(self, is_test_data_container=False):
        if is_test_data_container:
            text = "To determine the hyper-parameter (e.g. the number of features) of model, we applied cross validation " \
                   "with leave-one-out on the training data set. The hyper-parameters were set according to the model performance " \
                   "on the validation data set. "
        else:
            text = "To prove the performance of the model, we applied corss validation with leave-one-out on the data set. "

        return text

    def Run(self, data_container, test_data_container=DataContainer(), store_folder=''):
        train_pred_list, train_label_list, val_pred_list, val_label_list = [], [], [], []

        data = data_container.GetArray()
        label = data_container.GetLabel()
        case_name = data_container.GetCaseName()

        train_cv_info = [['CaseName', 'Pred', 'Label']]
        val_cv_info = [['CaseName', 'Pred', 'Label']]

        for train_index, val_index in self.__cv.split(data, label):
            train_data = data[train_index, :]
            train_label = label[train_index]
            val_data = data[val_index, :]
            val_label = label[val_index]

            self._classifier.SetData(train_data, train_label)
            self._classifier.Fit()

            train_prob = self._classifier.Predict(train_data)
            val_prob = self._classifier.Predict(val_data)

            for index in range(len(train_index)):
                train_cv_info.append(
                    [case_name[train_index[index]], train_prob[index], train_label[index]])
            for index in range(len(val_index)):
                val_cv_info.append([case_name[val_index[index]], val_prob[index], val_label[index]])

            train_pred_list.extend(train_prob)
            train_label_list.extend(train_label)
            val_pred_list.extend(val_prob)
            val_label_list.extend(val_label)

        total_train_label = np.asarray(train_label_list, dtype=np.uint8)
        total_train_pred = np.asarray(train_pred_list, dtype=np.float32)
        train_metric = EstimateMetirc(total_train_pred, total_train_label, 'train')

        total_label = np.asarray(val_label_list, dtype=np.uint8)
        total_pred = np.asarray(val_pred_list, dtype=np.float32)
        val_metric = EstimateMetirc(total_pred, total_label, 'val')

        self._classifier.SetDataContainer(data_container)
        self._classifier.Fit()

        test_metric = {}
        if test_data_container.GetArray().size > 0:
            test_data = test_data_container.GetArray()
            test_label = test_data_container.GetLabel()
            test_case_name = test_data_container.GetCaseName()
            test_pred = self._classifier.Predict(test_data)

            test_metric = EstimateMetirc(test_pred, test_label, 'test')

        if store_folder:
            if not os.path.exists(store_folder):
                os.mkdir(store_folder)

            info = {}
            info.update(train_metric)
            info.update(val_metric)

            np.save(os.path.join(store_folder, 'train_predict.npy'), total_train_pred)
            np.save(os.path.join(store_folder, 'val_predict.npy'), total_pred)
            np.save(os.path.join(store_folder, 'train_label.npy'), total_train_label)
            np.save(os.path.join(store_folder, 'val_label.npy'), total_label)

            with open(os.path.join(store_folder, 'train_cvloo_info.csv'), 'w', newline='') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerows(train_cv_info)
            with open(os.path.join(store_folder, 'val_cvloo_info.csv'), 'w', newline='') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerows(val_cv_info)

            if test_data_container.GetArray().size > 0:
                info.update(test_metric)
                np.save(os.path.join(store_folder, 'test_predict.npy'), test_pred)
                np.save(os.path.join(store_folder, 'test_label.npy'), test_label)

                test_result_info = [['CaseName', 'Pred', 'Label']]
                for index in range(len(test_label)):
                    test_result_info.append([test_case_name[index], test_pred[index], test_label[index]])
                with open(os.path.join(store_folder, 'test_info.csv'), 'w', newline='') as csvfile:
                    writer = csv.writer(csvfile)
                    writer.writerows(test_result_info)

            self._classifier.Save(store_folder)
            self.SaveResult(info, store_folder)

        return train_metric, val_metric, test_metric


class CrossValidation5Folder(CrossValidation):
    def __init__(self):
        super(CrossValidation5Folder, self).__init__()
        self.__cv = StratifiedKFold(5)

    def GetCV(self):
        return self.__cv

    def GetName(self):
        return '5-Folder'

    def GetDescription(self, is_test_data_container=False):
        if is_test_data_container:
            text = "To determine the hyper-parameter (e.g. the number of features) of model, we applied cross validation " \
                   "with 5-folder on the training data set. The hyper-parameters were set according to the model performance " \
                   "on the validation data set. "
        else:
            text = "To prove the performance of the model, we applied corss validation with 5-folder on the data set. "

        return text

    def Run(self, data_container, test_data_container=DataContainer(), store_folder=''):
        train_pred_list, train_label_list, val_pred_list, val_label_list = [], [], [], []

        data = data_container.GetArray()
        label = data_container.GetLabel()
        case_name = data_container.GetCaseName()
        group_index = 0

        train_cv_info = [['CaseName', 'Group', 'Pred', 'Label']]
        val_cv_info = [['CaseName', 'Group', 'Pred', 'Label']]

        for train_index, val_index in self.__cv.split(data, label):
            group_index += 1

            train_data = data[train_index, :]
            train_label = label[train_index]
            val_data = data[val_index, :]
            val_label = label[val_index]

            self._classifier.SetData(train_data, train_label)
            self._classifier.Fit()

            train_prob = self._classifier.Predict(train_data)
            val_prob = self._classifier.Predict(val_data)

            for index in range(len(train_index)):
                train_cv_info.append([case_name[train_index[index]], str(group_index), train_prob[index], train_label[index]])
            for index in range(len(val_index)):
                val_cv_info.append([case_name[val_index[index]], str(group_index), val_prob[index], val_label[index]])

            train_pred_list.extend(train_prob)
            train_label_list.extend(train_label)
            val_pred_list.extend(val_prob)
            val_label_list.extend(val_label)

        total_train_label = np.asarray(train_label_list, dtype=np.uint8)
        total_train_pred = np.asarray(train_pred_list, dtype=np.float32)
        train_metric = EstimateMetirc(total_train_pred, total_train_label, 'train')

        total_label = np.asarray(val_label_list, dtype=np.uint8)
        total_pred = np.asarray(val_pred_list, dtype=np.float32)
        val_metric = EstimateMetirc(total_pred, total_label, 'val')

        self._classifier.SetDataContainer(data_container)
        self._classifier.Fit()

        test_metric = {}
        if test_data_container.GetArray().size > 0:
            test_data = test_data_container.GetArray()
            test_label = test_data_container.GetLabel()
            test_case_name = test_data_container.GetCaseName()
            test_pred = self._classifier.Predict(test_data)

            test_metric = EstimateMetirc(test_pred, test_label, 'test')

        if store_folder:
            if not os.path.exists(store_folder):
                os.mkdir(store_folder)

            info = {}
            info.update(train_metric)
            info.update(val_metric)

            np.save(os.path.join(store_folder, 'train_predict.npy'), total_train_pred)
            np.save(os.path.join(store_folder, 'val_predict.npy'), total_pred)
            np.save(os.path.join(store_folder, 'train_label.npy'), total_train_label)
            np.save(os.path.join(store_folder, 'val_label.npy'), total_label)

            with open(os.path.join(store_folder, 'train_cv5_info.csv'), 'w', newline='') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerows(train_cv_info)
            with open(os.path.join(store_folder, 'val_cv5_info.csv'), 'w', newline='') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerows(val_cv_info)

            if test_data_container.GetArray().size > 0:
                info.update(test_metric)
                np.save(os.path.join(store_folder, 'test_predict.npy'), test_pred)
                np.save(os.path.join(store_folder, 'test_label.npy'), test_label)

                test_result_info = [['CaseName', 'Pred', 'Label']]
                for index in range(len(test_label)):
                    test_result_info.append([test_case_name[index], test_pred[index], test_label[index]])
                with open(os.path.join(store_folder, 'test_info.csv'), 'w', newline='') as csvfile:
                    writer = csv.writer(csvfile)
                    writer.writerows(test_result_info)

            self._classifier.Save(store_folder)
            self.SaveResult(info, store_folder)

        return train_metric, val_metric, test_metric

class CrossValidation10Folder(CrossValidation):
    def __init__(self):
        super(CrossValidation10Folder, self).__init__()
        self.__cv = StratifiedKFold(10)

    def GetCV(self):
        return self.__cv

    def GetName(self):
        return '10-Folder'

    def Run(self, data_container, test_data_container=DataContainer(), store_folder=''):
        train_pred_list, train_label_list, val_pred_list, val_label_list = [], [], [], []

        data = data_container.GetArray()
        label = data_container.GetLabel()
        case_name = data_container.GetCaseName()
        group_index = 0

        train_cv_info = [['CaseName', 'Group', 'Pred', 'Label']]
        val_cv_info = [['CaseName', 'Group', 'Pred', 'Label']]

        for train_index, val_index in self.__cv.split(data, label):
            group_index += 1

            train_data = data[train_index, :]
            train_label = label[train_index]
            val_data = data[val_index, :]
            val_label = label[val_index]

            self._classifier.SetData(train_data, train_label)
            self._classifier.Fit()

            train_prob = self._classifier.Predict(train_data)
            val_prob = self._classifier.Predict(val_data)

            for index in range(len(train_index)):
                train_cv_info.append(
                    [case_name[train_index[index]], str(group_index), train_prob[index], train_label[index]])
            for index in range(len(val_index)):
                val_cv_info.append([case_name[val_index[index]], str(group_index), val_prob[index], val_label[index]])

            train_pred_list.extend(train_prob)
            train_label_list.extend(train_label)
            val_pred_list.extend(val_prob)
            val_label_list.extend(val_label)

        total_train_label = np.asarray(train_label_list, dtype=np.uint8)
        total_train_pred = np.asarray(train_pred_list, dtype=np.float32)
        train_metric = EstimateMetirc(total_train_pred, total_train_label, 'train')

        total_label = np.asarray(val_label_list, dtype=np.uint8)
        total_pred = np.asarray(val_pred_list, dtype=np.float32)
        val_metric = EstimateMetirc(total_pred, total_label, 'val')

        self._classifier.SetDataContainer(data_container)
        self._classifier.Fit()

        test_metric = {}
        if test_data_container.GetArray().size > 0:
            test_data = test_data_container.GetArray()
            test_label = test_data_container.GetLabel()
            test_case_name = test_data_container.GetCaseName()
            test_pred = self._classifier.Predict(test_data)

            test_metric = EstimateMetirc(test_pred, test_label, 'test')

        if store_folder:
            if not os.path.exists(store_folder):
                os.mkdir(store_folder)

            info = {}
            info.update(train_metric)
            info.update(val_metric)

            np.save(os.path.join(store_folder, 'train_predict.npy'), total_train_pred)
            np.save(os.path.join(store_folder, 'val_predict.npy'), total_pred)
            np.save(os.path.join(store_folder, 'train_label.npy'), total_train_label)
            np.save(os.path.join(store_folder, 'val_label.npy'), total_label)

            with open(os.path.join(store_folder, 'train_cv10_info.csv'), 'w', newline='') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerows(train_cv_info)
            with open(os.path.join(store_folder, 'val_cv10_info.csv'), 'w', newline='') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerows(val_cv_info)

            if test_data_container.GetArray().size > 0:
                info.update(test_metric)
                np.save(os.path.join(store_folder, 'test_predict.npy'), test_pred)
                np.save(os.path.join(store_folder, 'test_label.npy'), test_label)

                test_result_info = [['CaseName', 'Pred', 'Label']]
                for index in range(len(test_label)):
                    test_result_info.append([test_case_name[index], test_pred[index], test_label[index]])
                with open(os.path.join(store_folder, 'test_info.csv'), 'w', newline='') as csvfile:
                    writer = csv.writer(csvfile)
                    writer.writerows(test_result_info)

            self._classifier.Save(store_folder)
            self.SaveResult(info, store_folder)

        return train_metric, val_metric, test_metric

    def GetDescription(self, is_test_data_container=False):
        if is_test_data_container:
            text = "To determine the hyper-parameter (e.g. the number of features) of model, we applied cross validation " \
                   "with 10-folder on the training data set. The hyper-parameters were set according to the model performance " \
                   "on the validation data set. "
        else:
            text = "To prove the performance of the model, we applied corss validation with 10-folder on the data set. "

        return text



