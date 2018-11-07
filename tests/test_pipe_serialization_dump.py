# -*- coding: utf-8 -*-

import unittest
import logging

from collections import OrderedDict
from os import path, listdir
from tempfile import TemporaryDirectory

import numpy as np
from sklearn.pipeline import Pipeline, FeatureUnion
from sklearn.decomposition import TruncatedSVD, PCA
from sklearn.preprocessing import MinMaxScaler

from gordo_components.model.models import KerasModel
from gordo_components.pipeline_translator import pipeline_serializer


logger = logging.getLogger(__name__)


class PipelineDumpTestCase(unittest.TestCase):

    def _structure_verifier(self, prefix_dir, structure):
        """
        Recursively check directory / file structure as represented in an
        OrderedDict
        """
        for directory, file_or_dict in structure.items():

            # Join the prefix_dir to the relative directory for this key/value
            directory = path.join(prefix_dir, directory)

            logger.debug(f'Prefix dir listing: {listdir(prefix_dir)}')
            logger.debug(f'Dir: {directory}')
            logger.debug(f'File or dict: {file_or_dict}')
            logger.debug(f'Files in dir: {listdir(directory)}')
            logger.debug('-' * 30)

            self.assertTrue(path.isdir(directory))

            # If this is an OrderedDict, then it's another subdirectory struct
            if isinstance(file_or_dict, OrderedDict):
                self._structure_verifier(directory, file_or_dict)
            else:

                # Otherwise we just need to verify that this is indeed a file
                self.assertTrue(path.isfile(path.join(directory, file_or_dict)))

    def test_pipeline_serialization(self):
        pipe = Pipeline([
            ('pca1', PCA(n_components=10)),
            ('fu', FeatureUnion([
                ('pca2', PCA(n_components=3)),
                ('pipe', Pipeline([
                    ('minmax', MinMaxScaler()),
                    ('truncsvd', TruncatedSVD(n_components=7))
                ]))
            ])),
            ('ae', KerasModel(kind='feedforward_symetric'))
        ])

        X = np.random.random(size=100).reshape(10, 10)
        pipe.fit(X, X)

        with TemporaryDirectory() as tmp:
            pipeline_serializer.dump(pipe, tmp)

            # Assert that a dirs are created for each step in Pipeline
            expected_structure = OrderedDict([
                ('n_step=000-class=sklearn.pipeline.Pipeline', OrderedDict([
                    ('n_step=000-class=sklearn.decomposition.pca.PCA', 'pca1.pkl.gz'),

                    ('n_step=001-class=sklearn.pipeline.FeatureUnion', 'params.json'),
                    ('n_step=001-class=sklearn.pipeline.FeatureUnion', OrderedDict([
                        ('n_step=000-class=sklearn.decomposition.pca.PCA', 'pca2.pkl.gz'),

                        ('n_step=001-class=sklearn.pipeline.Pipeline', OrderedDict([
                            ('n_step=000-class=sklearn.preprocessing.data.MinMaxScaler', 'minmax.pkl.gz'),
                            ('n_step=001-class=sklearn.decomposition.truncated_svd.TruncatedSVD', 'truncsvd.pkl.gz')
                        ]))
                    ])),
                    ('n_step=002-class=gordo_components.model.models.KerasModel', 'model.h5'),
                    ('n_step=002-class=gordo_components.model.models.KerasModel', 'params.json')
                ]))
            ])

            self._structure_verifier(prefix_dir=tmp, structure=expected_structure)
