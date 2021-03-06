#!/usr/bin/env python
# -*- coding:utf-8 -*-

import json

from base import SpecialFormatter
from datetime import datetime
from imgkit import ImageKit
from network import Network
from urlutils import JsonResult
from utils import getProperty, randomSleep, OutputPath

class Searcher:

    def __init__(self, configFile, qwd):

        self.qwd = qwd

        self.url = getProperty(configFile, 'search-url')
        self.configFile = configFile

    def create(self, data):

        result = dict()

        formatter = SpecialFormatter.create(data)

        result['plate'] = formatter.getPlate(self.qwd)

        if formatter.plateShareUrl is None:
            return None

        result['image'] = formatter.skuimgurl

        return result

    def search(self, content):

        r = Network.post(self.url, data={'content': content})

        if r is None:
            print 'No result for', content
            return False

        try:
            obj = json.loads(r.content.decode('utf-8', 'ignore'))
        except ValueError as e:
            print 'Error (', e, ') of json: "', r.content, '"'
            return False

        num = obj['num']
        if num is 0:
            print 'Error content: "', r.content, '"'
            return False

        print 'Found', num, 'SKU with "', content, '"'

        datas = obj['list']

        plates = list()
        urls = list()

        for data in datas:

            formatter = SpecialFormatter.create(data)

            plate = formatter.getPlate(self.qwd)
            url = data['skuimgurl']

            plates.append(plate)
            urls.append(url)

        now = datetime.now().strftime('%Y_%m_%d_%H_%M_%S')
        path = OutputPath.getDataPath('search_{}'.format(now), 'jpeg')

        self.plate = '\n----------------------------\n'.join(plates)
        self.image = ImageKit.concatUrlsTo(path, urls)

        return True

    def explore(self, content):

        if content is None:
            return JsonResult.error(-101, 'Empty inputted content')

        r = Network.post(self.url, data={'content': content})

        if r is None:
            print 'No result for', content
            return JsonResult.error(-102, 'No result')

        try:
            obj = json.loads(r.content.decode('utf-8', 'ignore'))
        except ValueError as e:
            print 'Error (', e, ') of json: "', r.content, '"'
            return JsonResult.error(-103, 'Parse result error')

        num = obj['num']
        if num is 0:
            print 'Error content: "', r.content, '"'
            return JsonResult.error(-104, 'No result')

        print 'Found', num, 'SKUs with "', content, '"'

        # Get all
        dataList = list()

        for special in obj.pop('list'):

            data = self.create(special)

            if data is not None:
                dataList.append(data)

            randomSleep(1, 2)

        obj['num'] = len(dataList)
        obj['list'] = dataList

        return JsonResult.succeed(obj)

class Viewer:

    def __init__(self, configFile, qwd):

        self.qwd = qwd

        self.imageType = int(getProperty(configFile, 'share-image-type'))

    def create(self, data):

        result = dict()

        formatter = SpecialFormatter.create(data)

        result['plate'] = formatter.getPlate(self.qwd)

        if formatter.plateShareUrl is None:
            return None

        result['image'] = formatter.skuimgurl

        return result

    def get(self, shareFile, index=0):

        with open(shareFile, 'r') as fp:
            content = fp.read()

        try:
            obj = json.loads(content.decode('utf-8', 'ignore'))
        except ValueError as e:
            raise Exception('{} is not valid config file.'.format(shareFile))

        if index >= 0 and index < obj['num']: # Get one
            data = self.create(obj['list'][index])
            return JsonResult.succeed(data)

        # Get all
        dataList = list()

        for special in obj.pop('list'):

            data = self.create(special)

            if data is not None:
                dataList.append(data)

            randomSleep(1, 2)

        obj['num'] = len(dataList)
        obj['list'] = dataList

        return JsonResult.succeed(obj)


