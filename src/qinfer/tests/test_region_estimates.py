#!/usr/bin/python
# -*- coding: utf-8 -*-
##
# test_region_estimates.py: Checks that computed credible regions are working.
##
# © 2014 Chris Ferrie (csferrie@gmail.com) and
#        Christopher E. Granade (cgranade@gmail.com)
#
# This file is a part of the Qinfer project.
# Licensed under the AGPL version 3.
##
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
##

## FEATURES ###################################################################

from __future__ import absolute_import
from __future__ import division # Ensures that a/b is always a float.

## IMPORTS ####################################################################

import numpy as np
from numpy.testing import assert_equal, assert_almost_equal, assert_array_less

from qinfer.abstract_model import FiniteOutcomeModel
from qinfer.tests.base_test import DerandomizedTestCase
from qinfer.distributions import MultivariateNormalDistribution
from qinfer.smc import SMCUpdater

## FUNCTIONS ##################################################################

def unique_rows(a):
    """
    Discards duplicate rows.
    """
    # from http://stackoverflow.com/a/16971324/1082565
    ind = np.lexsort(a.T)
    return a[ind[np.concatenate(([True],np.any(a[ind[1:]]!=a[ind[:-1]],axis=1)))]]

## CLASSES ####################################################################

class MockModel(FiniteOutcomeModel):
    """
    Two-outcome model whose likelihood is always 0.5, irrespective of
    model parameters, outcomes or experiment parameters. We are allowed to
    specify any number of model parameters.
    """

    def __init__(self, n_mps):
        self._n_mps = n_mps
        super(MockModel, self).__init__()
    
    @property
    def n_modelparams(self):
        return self._n_mps
        
    @staticmethod
    def are_models_valid(modelparams):
        return np.ones((modelparams.shape[0], ), dtype=bool)
        
    @property
    def is_n_outcomes_constant(self):
        return True
        
    def n_outcomes(self, expparams):
        return 2
        
    @property
    def expparams_dtype(self):
        return [('a', float), ('b', int)]
          
    def likelihood(self, outcomes, modelparams, expparams):
        super(MockModel, self).likelihood(outcomes, modelparams, expparams)
        pr0 = np.ones((modelparams.shape[0], expparams.shape[0])) / 2
        return FiniteOutcomeModel.pr0_to_likelihood_array(outcomes, pr0)

class TestCredibleRegions(DerandomizedTestCase):

    N_PARTICLES = 10000
    N_MPS = 4
    MEAN = np.array([2,3,5,7])
    COV = np.array([[1,0,0,0.5],[0,1,0.2,0],[0,0.2,2,0],[0.5,0,0,1]])
    SLICE = np.s_[:2]

    def test_est_credible_region(self):
        """
        Tests that est_credible_region doesn't fail miserably
        """
        dist = MultivariateNormalDistribution(self.MEAN, self.COV)
        # the model is irrelevant; we just want the updater to have some particles
        # with the desired normal distribution.
        u = SMCUpdater(MockModel(self.N_MPS), self.N_PARTICLES, dist)

        # first check that 0.95 confidence points consume 0.9 confidence points 
        points1 = u.est_credible_region(level=0.95)
        points2 = u.est_credible_region(level=0.9)
        assert_almost_equal(
            np.sort(unique_rows(np.concatenate([points1, points2])), axis=0), 
            np.sort(points1, axis=0)
        )

        # do the same thing with different slice
        points1 = u.est_credible_region(level=0.95, modelparam_slice=self.SLICE)
        points2 = u.est_credible_region(level=0.9, modelparam_slice=self.SLICE)
        assert_almost_equal(
            np.sort(unique_rows(np.concatenate([points1, points2])), axis=0), 
            np.sort(points1, axis=0)
        )

    def test_region_est_hull(self):
        """
        Tests that test_region_est_hull works
        """
        dist = MultivariateNormalDistribution(self.MEAN, self.COV)
        # the model is irrelevant; we just want the updater to have some particles
        # with the desired normal distribution.
        u = SMCUpdater(MockModel(self.N_MPS), self.N_PARTICLES, dist)

        faces, vertices = u.region_est_hull(level=0.95)

        # In this multinormal case, the convex hull surface 
        # should be centered at MEAN
        assert_almost_equal(
            np.round(np.mean(vertices, axis=0)), 
            np.round(self.MEAN)
        )
        
        # And a lower level should result in a smaller hull
        # and therefore smaller sample variance
        faces2, vertices2 = u.region_est_hull(level=0.2)
        assert_array_less(np.var(vertices2, axis=0), np.var(vertices, axis=0))

    def test_region_est_ellipsoid(self):
        """
        Tests that region_est_ellipsoid works.
        """

        #dist = MultivariateNormalDistribution(self.MEAN, self.COV)
        dist = MultivariateNormalDistribution(self.MEAN, self.COV)
        # the model is irrelevant; we just want the updater to have some particles
        # with the desired normal distribution.
        u = SMCUpdater(MockModel(4), self.N_PARTICLES, dist)

        # ask for a confidence level of 0.5
        A, c = u.region_est_ellipsoid(level=0.5)

        # center of ellipse should be the mean of the multinormal
        assert_almost_equal(np.round(c), self.MEAN, 1)

        # finally, the principal lengths of the ellipsoid 
        # should be the same as COV
        _, QA, _ = np.linalg.svd(A)
        _, QC, _ = np.linalg.svd(self.COV)
        QA, QC = np.sqrt(QA), np.sqrt(QC)
        assert_almost_equal(
            QA / np.linalg.norm(QA),
            QC / np.linalg.norm(QC),
            1   
        )