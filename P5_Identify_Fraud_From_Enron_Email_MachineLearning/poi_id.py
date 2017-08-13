# coding: utf-8

from __future__ import print_function
import sys
print(sys.version)
sys.path.append("../tools")

import random 

from sklearn.feature_selection import SelectKBest
from sklearn import preprocessing
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, precision_score, recall_score, classification_report
from sklearn.model_selection import GridSearchCV

from sklearn.linear_model import LogisticRegression
from sklearn.naive_bayes import GaussianNB
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier, AdaBoostClassifier
from sklearn.neural_network import MLPClassifier
from sklearn.neighbors import KNeighborsClassifier

from feature_format import featureFormat, targetFeatureSplit
from tester import dump_classifier_and_data, test_classifier

import pickle
import numpy as np
import matplotlib.pyplot as plt

with open("final_project_dataset.pkl", "rb") as data_file:
    dataset = pickle.load(data_file)

# ### Task 1: Select what features you'll use.
### features_list is a list of strings, each of which is a feature name.
### The first feature must be "poi".
features_list = ['poi','salary'] # You will need to use more features

# brief check for outliers
salaries, pois = [], []
for k, v in dataset.items():
    salaries.append(v['salary'])
    pois.append(v['poi'] * 10000000)  # multiply for visual scale

# plt.figure(figsize=(30,5))
# plt.plot(salaries)
# plt.plot(pois)
# plt.show()

# ### Task 2: Remove outliers
# extreme outlier with salary 25M +
# check it's key name
for k, v in dataset.items():
    if v['salary'] != 'NaN' and v['salary'] > 10000000:
        print(k)

# remove "TOTAL" row from the dataset
del dataset['TOTAL']

# get all dict keys
all_features = list(list(dataset.items())[0][1].keys())
print('All features:', all_features)

# email address is pretty much useless
del all_features[all_features.index('email_address')]

# ### Task 3: Create new feature(s)

# a feature to represent ratio of person's correspondence with poi to their total correspondence
for k, v in dataset.items():
    if any([v['from_poi_to_this_person']=='NaN', v['from_this_person_to_poi']=='NaN', v['to_messages']=='NaN', v['from_messages']=='NaN']):
        v['interaction_with_poi'] = 'NaN'
    else:
        v['interaction_with_poi'] = (v['from_poi_to_this_person'] + v['from_this_person_to_poi']) / (v['to_messages'] + v['from_messages'])

# ratio of deferral payments to total payments
for k, v in dataset.items():
    if any([v['deferral_payments']=='NaN', v['total_payments']=='NaN']):
        v['payments_ratio'] = 'NaN'
    else:
        v['payments_ratio'] = v['deferral_payments'] / v['total_payments']

# ratio of income to total payments
for k, v in dataset.items():
    if any([v['salary']=='NaN', v['total_payments']=='NaN', v['bonus']=='NaN']):
        v['salary_payments_ratio'] = 'NaN'
    else:
        v['salary_payments_ratio'] = v['total_payments'] / v['salary'] + v['bonus']

# once again pick all features
all_features = list(list(dataset.items())[0][1].keys())
del all_features[all_features.index('email_address')]

# ensure poi will be in first place so lables and features could be succesfully formed with featureFormat
my_features = ['poi'] + [f for f in all_features if f != 'poi']

data = featureFormat(dataset, my_features, sort_keys = True)
labels, features = targetFeatureSplit(data)

# normalize
features = preprocessing.scale(features)

# check for best features using sklearn's SelectKBest
# pick 5 features
k_best = SelectKBest(k=5)
k_best.fit(features, labels)

# create a new feature list
feature_list = ['poi']
for f in sorted(zip(k_best.get_support(), my_features[1:]), reverse=True)[:5]:
    print(f[1], f[0])
    feature_list.append(f[1])

# ### Task 4: Try a varity of classifiers

clf = GaussianNB()
print(test_classifier(clf, dataset, feature_list))

clf = LogisticRegression()
print(test_classifier(clf, dataset, feature_list))

clf = RandomForestClassifier()
print(test_classifier(clf, dataset, feature_list))

clf = MLPClassifier()
print(test_classifier(clf, dataset, feature_list))

clf = KNeighborsClassifier()
print(test_classifier(clf, dataset, feature_list))

clf = GradientBoostingClassifier()
print(test_classifier(clf, dataset, feature_list))

clf = AdaBoostClassifier()
print(test_classifier(clf, dataset, feature_list))

# ### Task 5: Tune your classifier to achieve better than .3 precision and recall

# prepare the data for testing
data = featureFormat(dataset, feature_list, sort_keys = True)
y, X = targetFeatureSplit(data)

# create parameter array - list of tuples with two numbers, representing probabilites, which sum up to 1
priors = [(round(i / 20., 2), round(1 - (i / 20.), 2),) for i in range(1, 20)]
print('Parameter grid:', priors)

# split data into training and testing sets
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.33)

parameters = {'priors': priors}
scores = ['precision', 'recall']

# perform GridSearchCV - results may vary due to random nature
for score in scores:
    print("# Tuning hyper-parameters for %s" % score)
    clf = GridSearchCV(GaussianNB(), parameters, cv=10, scoring='%s_macro' % score)
    clf.fit(X_train, y_train)
    print("Best parameters set found on development set:")
    print(clf.best_params_)
    print("Grid scores on development set:")
    means = clf.cv_results_['mean_test_score']
    stds = clf.cv_results_['std_test_score']
    for mean, std, params in zip(means, stds, clf.cv_results_['params']):
        print("%0.3f (+/-%0.03f) for %r" % (mean, std * 2, params))
    print("\n\nDetailed classification report:\n")
    print("The model is trained on the full development set.")
    print("The scores are computed on the full evaluation set.\n")
    y_pred = clf.predict(X_test)
    print(classification_report(y_test, y_pred))

# #### However In the real world scenario predict_proba might be used for classifying classes with different error significance

clf = GaussianNB(priors=(0.25, 0.75))
test_classifier(clf, dataset, feature_list)

dump_classifier_and_data(clf, dataset, feature_list)

# #### A pipeline would look like this

from sklearn.feature_selection import SelectKBest
from sklearn.feature_selection import f_regression
from sklearn.pipeline import Pipeline

anova_filter = SelectKBest(f_regression, k=5)
clf = GaussianNB()
anova_gnb = Pipeline([('anova', anova_filter), ('gnb', clf)])
anova_gnb.set_params(gnb__priors=(0.25, 0.75))

test_classifier(anova_gnb, dataset, feature_list)
