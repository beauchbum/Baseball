from flask import Flask , url_for, request, flash
import sys
import os
reload(sys)
sys.setdefaultencoding("utf-8")
from flask import Flask , url_for, request, flash
from flask import render_template, make_response, redirect, url_for
from flask import Response
from flask import send_file, jsonify
from google.cloud import storage
import MySQLdb
reload(sys)
sys.setdefaultencoding("utf-8")
import logging
import traceback
import re

import sklearn
import nltk
from nltk.corpus import PlaintextCorpusReader, stopwords
from nltk.tokenize import sent_tokenize, word_tokenize
from gensim.models import Word2Vec
import glob
import numpy as np
import time
import datetime
from google.auth import compute_engine
import requests
import json









logging.getLogger().setLevel(logging.DEBUG)

app = Flask(__name__, instance_relative_config=True)
app.config.from_pyfile('config.py')
app.secret_key = 'some_secret'
GOOGLE_APPLICATION_CREDENTIALS = app.config['GOOGLE_APPLICATION_CREDENTIALS']
CLOUDSQL_PROJECT = app.config['CLOUDSQL_PROJECT']

from oauth2client.contrib.gce import AppAssertionCredentials
from oauth2client.service_account import ServiceAccountCredentials





try:
    CLOUD_STORAGE_BUCKET = os.environ['CLOUD_STORAGE_BUCKET']
except:
    CLOUD_STORAGE_BUCKET = "analytics_data_extraction"

def cloud_sql_connect():

    cloud_dbpass = app.config['DBPASS']
    cloud_dbhost = app.config['DBHOST']
    cloud_dbuser = app.config['DBUSER']
    cloud_dbname = app.config['DBNAME']
    cloud_dbport = app.config['DBPORT']
    CLOUDSQL_PROJECT = app.config['CLOUDSQL_PROJECT']
    CLOUDSQL_INSTANCE = app.config['CLOUDSQL_INSTANCE']

    conn = MySQLdb.connect(unix_socket='/cloudsql/{}:{}'.format(CLOUDSQL_PROJECT, CLOUDSQL_INSTANCE), user=cloud_dbuser,
                               host=cloud_dbhost, passwd=cloud_dbpass, db=cloud_dbname)

    return conn



@app.route('/', methods=['GET', 'POST'])
def index():

    source = "local"
    try:
        #gcs = storage.Client(project=CLOUDSQL_PROJECT, credentials=compute_engine.Credentials())
        gcs = storage.Client()
        bucket = gcs.get_bucket('analytics_data_extraction')
        source = "cloud"
    except Exception as e:
        logging.info("Dev Server")
        pass



    def read_training_data(files, source):

        tokenizer = nltk.data.load('tokenizers/punkt/english.pickle')
        data = []
        files_count = 0
        files = list(set(files))

        if source == "local":

            for file in files:
                try:
                    path = "LocalDocs/" + file.split("/")[-1]
                    fp = open(path)
                    data.append(fp.read())
                    fp.close()
                    files_count+=1
                except Exception as e:
                    logging.info("Unable to open local file %s" % file)
        else:
            for file in files:
                file_split = file.split("/")
                fname = file_split[-2] + "/" + file_split[-1]
                try:
                    blob = bucket.get_blob(fname)
                    data.append(blob.download_as_string())
                    files_count+=1
                except:
                    logging.info("Unable to open cloud file %s" % fname)

        training_data = []
        for doc in data:
            s = unicode(doc, errors='ignore')
            s = s.lower()

            sents_token = [re.sub('[^a-zA-Z]', " ", x) for x in tokenizer.tokenize(s)]
            training_data += [x.split() for x in [sentence for sentence in sents_token]]
        return training_data, files_count

    def train_model(data, model_name):
        num_features = 300
        min_word_count = 10  # Minimum word count
        num_workers = 4  # Number of threads to run in parallel
        context = 10  # Context window size
        downsampling = 1e-3  # Downsample setting for frequent words

        # Initialize and train the model (this will take some time)
        from gensim.models import word2vec
        print "Training model..."
        model = word2vec.Word2Vec(data, workers=num_workers, \
                                  size=num_features, min_count=min_word_count, \
                                  window=context, sample=downsampling)

        # If you don't plan to train the model any further, calling
        # init_sims will make the model much more memory-efficient.
        model.init_sims(replace=True)

        # It can be helpful to create a meaningful model name and
        # save the model for later use. You can load it later using Word2Vec.load()

        model.save(model_name)
        return model


    conn = cloud_sql_connect()
    cursor = conn.cursor()
    try:
        project_ID = request.form['project_id']
        form_files = request.form.getlist('form_files')
        logging.info("FORM FILES: %s" % (form_files))
        model_name = request.form['model_name']
        num_features = 300

        relevant_files = []
        query = "select distinct ID, file_name, encrypted from CE_Files where project_ID = %s and active=1 and ID in %s"
        param = [project_ID, tuple(form_files)]
        cursor.execute(query, param)
        res = cursor.fetchall()
        for r in res:
            relevant_files.append(r[1])

        training_data, files_count = read_training_data(relevant_files, source)
        model = train_model(training_data, model_name)
        query = "Update CE_Models set active=0 where model_name=%s"
        param = [model_name]
        cursor.execute(query, param)

        query = "Insert into CE_Models (ID, model_name, project_ID, active, created, number_files) Values ((Select count(1) + 1 from CE_Models fds), %s, %s, 1, (select now()), %s)"
        param = [model_name, project_ID, files_count]
        cursor.execute(query, param)

        conn.commit()


    except Exception as e:
        logging.info(traceback.format_exc())

    cursor.close();
    conn.close()

    return "test"

@app.route('/run_model_concept', methods=['GET', 'POST'])
def run_model_concept():

    source = "local"
    try:
        #gcs = storage.Client(project=CLOUDSQL_PROJECT, credentials=compute_engine.Credentials())
        gcs = storage.Client()
        bucket = gcs.get_bucket('analytics_data_extraction')
        source = "cloud"
    except Exception as e:
        logging.info("Dev Server")
        pass


    num_features = 300

    def makeFeatureVec(words, model, num_features):
        featureVec = np.zeros((num_features,), dtype="float32")

        nwords = 0.
        index2word_set = set(model.wv.index2word)
        for word in words:
            if word in index2word_set:
                nwords = nwords + 1.
                featureVec = np.add(featureVec, model[word])
        if nwords>0:
            featureVec = np.divide(featureVec, nwords)
        return featureVec

    def my_cosine_similarity(test_vect, phrase):
        sim = np.dot(test_vect, phrase) / (np.linalg.norm(test_vect) * np.linalg.norm(phrase))
        return float(sim)

    def format_sentence(sent):
        s = unicode(sent, errors='ignore')
        s = s.lower()
        stops = set(stopwords.words("english"))
        s = re.sub('[^a-zA-Z]', " ", s).split()
        stripped_sent = []
        for word in s:
            if word not in stops:
                stripped_sent.append(word)
        return stripped_sent

    def read_testing(file, source):

        data = []
        tokenizer = nltk.data.load('tokenizers/punkt/english.pickle')
        file_split = file.split("/")


        if source == "local":
            fname = file_split[-1]
            txt_path_list = glob.glob("LocalDocs" + '/*.txt')

            for path in txt_path_list:
                path = path.replace('\\', '/')
                if path.split("/")[-1] == fname:
                    fp = open(path)
                    logging.info("File Read")
                    data.append(fp.read())
                    fp.close()
        else:
            try:
                fname = file_split[-2] + "/" + file_split[-1]
                blob = bucket.get_blob(fname)
                data.append(blob.download_as_string())
            except Exception as e:
                logging.info("Something went wrong when reading data from cloud: %s" % e)

        words = []
        raw_sentences = []
        testing_data = []
        stops = set(stopwords.words("english"))


        for doc in data:
            s = unicode(doc, errors='ignore')
            s = s.lower()

            raw_sentences = tokenizer.tokenize(s)
            sentences = [re.sub('[^a-zA-Z]', " ", x).split() for x in raw_sentences]
            real_sentences = []
            for sentence in sentences:
                stripped_sent = []
                for word in sentence:
                    if word not in stops:
                        stripped_sent.append(word)
                real_sentences.append(stripped_sent)
            testing_data += real_sentences
        return raw_sentences, testing_data

    project_ID = request.form['project_id']
    form_files = request.form.getlist('form_files')
    model_name = request.form['model_name']
    model_ID = request.form['model_ID']
    concept_ID = request.form['concept_ID']
    user_email = request.form['user_email']
    threshold = float(request.form['threshold'])



    logging.info(threshold)
    logging.info(model_name)

    model = Word2Vec.load(model_name)

    cloud_conn = cloud_sql_connect()
    cloud_cursor = cloud_conn.cursor()

    hash = "%s%d" % (user_email.lower(), int(time.time()))
    start_time_stamp = datetime.datetime.today().strftime('%Y-%m-%d %H:%M:%S')
    start_time = int(time.time())
    files_processed = 0
    regexes_used = 0
    total_data_scanned = 0

    run_query = "Insert into CE_Model_Runs (ID, project_ID, threshold, model_ID, start_time, end_time, files_processed, phrases_used, active, concept_ID, hash) values ((select count(1) from CE_Model_Runs a),%s,%s,%s,%s,%s,0,0,1,%s,%s)"


    query = "select ID, phrase from CE_Phrases where concept_ID = %s and active = 1"
    param = [concept_ID]
    cloud_cursor.execute(query, param)
    phrases = cloud_cursor.fetchall()
    stripped_phrases = []
    for p in phrases:
        stripped_phrases.append((p[0], format_sentence(p[1])))

    queries = []
    params = []



    relevant_files = []
    query = "select distinct ID, file_name, encrypted from CE_Files where project_ID = %s and active=1 and ID in %s"
    param = [project_ID, tuple(form_files)]
    cloud_cursor.execute(query, param)
    res = cloud_cursor.fetchall()
    for r in res:
        original_data,testing_data = read_testing(r[1], source)
        test_vectors = []
        for i in range(len(testing_data)):
            for phrase in stripped_phrases:
                test_vect = makeFeatureVec(testing_data[i], model, num_features)
                phrase_vect = makeFeatureVec(phrase[1], model, num_features)
                cosine = my_cosine_similarity(test_vect, phrase_vect)
                if cosine >= threshold:
                    logging.info(testing_data[i])
                    queries.append("insert into CE_Model_Output (ID, file_ID, phrase_ID, model_ID, big_text_value, active, execution_hash, cosine_similarity) values ((select count(1) from CE_Model_Output a), %s,%s,%s,%s,1,%s,%s)")
                    val = str(original_data[i]).replace(chr(13), "").replace(chr(10), "")
                    params.append([r[0], phrase[0], model_ID, val, hash, cosine])

    for i, (q, p) in enumerate(zip(queries, params)):
        cloud_cursor.execute(q,p)

    end_time_stamp = datetime.datetime.today().strftime('%Y-%m-%d %H:%M:%S')
    run_param = [project_ID, threshold, model_ID, start_time_stamp, end_time_stamp, -1, hash]
    try:
        cloud_cursor.execute(run_query, run_param)
    except Exception as e:
        logging.info(e)
        logging.info(run_param)

    cloud_conn.commit()
    cloud_cursor.close(); cloud_conn.close()
    logging.info("RYAN - CHANGES COMMITTED")

    return "test"

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5000, debug=True, threaded=True)

