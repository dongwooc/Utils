import pdb
import six
import numpy as np
from astropy.io import fits
import astropy.units as u
from utils import bin_ndarray as rebin
from utils import gauss_kern
from utils import clean_nans
from utils import clean_args
from astropy import cosmology
from astropy.cosmology import Planck15 as cosmo
from astropy.cosmology import z_at_value

class Skymaps:

	def __init__(self,file_map,file_noise,psf,color_correction=1.0):
		''' This Class creates Objects for a set of maps/noisemaps/beams/TransferFunctions/etc., 
		at each Wavelength.
		This is a work in progress!
		Issues:  If the beam has a different pixel size from the map, it is not yet able to 
		re-scale it.  Just haven't found a convincing way to make it work.   
		Future Work:
		Will shift some of the work into functions (e.g., read psf, color_correction) 
		and increase flexibility.
		'''
		#READ MAPS
		if file_map == file_noise:
			#SPIRE Maps have Noise maps in the second extension.  
			cmap, hd = fits.getdata(file_map, 1, header = True)
			cnoise, nhd = fits.getdata(file_map, 2, header = True)
		else:
			#This assumes that if Signal and Noise are different maps, they are contained in first extension
			cmap, hd = fits.getdata(file_map, 0, header = True)
			cnoise, nhd = fits.getdata(file_noise, 0, header = True)

		#GET MAP PIXEL SIZE	
		if 'CD2_2' in hd:
			pix = hd['CD2_2'] * 3600.
		else:
			pix = hd['CDELT2'] * 3600.

		#READ BEAMS
		#Check first if beam is a filename (actual beam) or a number (approximate with Gaussian)
		if isinstance(psf, six.string_types):
			beam, phd = fits.getdata(psf, 0, header = True)
			#GET PSF PIXEL SIZE	
			if 'CD2_2' in phd:
				pix_beam = phd['CD2_2'] * 3600.
			elif 'CDELT2' in phd:
				pix_beam = phd['CDELT2'] * 3600.
			else: pix_beam = pix
			#SCALE PSF IF NECESSARY 
			if np.round(10.*pix_beam) != np.round(10.*pix):
				raise ValueError("Beam and Map have different size pixels")
				scale_beam = pix_beam / pix
				pms = np.shape(beam)
				new_shape=(np.round(pms[0]*scale_beam),np.round(pms[1]*scale_beam))
				pdb.set_trace()
				kern = rebin(clean_nans(beam),new_shape=new_shape,operation='ave')
				#kern = rebin(clean_nans(beam),new_shape[0],new_shape[1])
			else: 
				kern = clean_nans(beam)
			self.psf_pixel_size = pix_beam
		else:
			sig = psf / 2.355 / pix
			kern = gauss_kern(psf, np.floor(psf * 8.), pix)

		self.map = clean_nans(cmap) * color_correction
		self.noise = clean_nans(cnoise,replacement_char=1e10) * color_correction
		self.header = hd
		self.pixel_size = pix
		self.psf = kern

	def beam_area_correction(self,beam_area):
		self.map *= beam_area * 1e6
		
	def add_wavelength(self,wavelength):
		self.wavelength = wavelength

	def add_fwhm(self,fwhm):
		self.fwhm = fwhm

	def add_weights(self,file_weights):
		weights, whd = fits.getdata(file_weights, 0, header = True)
		#pdb.set_trace()
		self.noise = clean_nans(1./weights,replacement_char=1e10)


class Field_catalogs:
	def __init__(self, tbl):
		self.table = tbl
		self.nsrc = len(tbl)
		self.id_z_ms_pop = {}

	def separate_sf_qt(self):
		sfg = np.ones(self.nsrc)
		#pdb.set_trace()
		for i in range(self.nsrc):
			if (self.table.rf_U_V.values[i] > 1.3) and (self.table.rf_V_J.values[i] < 1.5):
				if (self.table.z_peak.values[i] < 1):
					if (self.table.rf_U_V.values[i] > (self.table.rf_V_J.values[i]*0.88+0.69) ): sfg[i]=0
				if (self.table.z_peak.values[i] > 1):
					if (self.table.rf_U_V.values[i] > (self.table.rf_V_J.values[i]*0.88+0.59) ): sfg[i]=0
		#indsf = np.where(sfg == 1)
		#indqt = np.where(sfg == 0)
		self.table['sfg'] = sfg

	def separate_sf_qt_agn(self,Fcut = 20):
		sfg = np.ones(self.nsrc)
		#pdb.set_trace()
		#AGN
		for i in range(self.nsrc):
			if (self.table.F_ratio[i] >= Fcut): 
				sfg[i]=2
			else:
				if (self.table.rf_U_V.values[i] > 1.3) and (self.table.rf_V_J.values[i] < 1.5):
					if (self.table.z_peak.values[i] < 1):
						if (self.table.rf_U_V.values[i] > (self.table.rf_V_J.values[i]*0.88+0.69) ): sfg[i]=0
					if (self.table.z_peak.values[i] > 1):
						if (self.table.rf_U_V.values[i] > (self.table.rf_V_J.values[i]*0.88+0.59) ): sfg[i]=0
		#indsf = np.where(sfg == 1)
		#indqt = np.where(sfg == 0)
		self.table['sfg'] = sfg

	def separate_sf_qt_agn_Ahat(self,Fcut = 20, Ahat = 0.5):
		sfg = np.ones(self.nsrc)
		#pdb.set_trace()
		#AGN
		for i in range(self.nsrc):
			if (self.table.F_ratio[i] >= Fcut) & (self.table.a_hat_AGN[i] >= Ahat): 
				sfg[i]=2
			else:
				if (self.table.rf_U_V.values[i] > 1.3) and (self.table.rf_V_J.values[i] < 1.5):
					if (self.table.z_peak.values[i] < 1):
						if (self.table.rf_U_V.values[i] > (self.table.rf_V_J.values[i]*0.88+0.69) ): sfg[i]=0
					if (self.table.z_peak.values[i] > 1):
						if (self.table.rf_U_V.values[i] > (self.table.rf_V_J.values[i]*0.88+0.59) ): sfg[i]=0
		#indsf = np.where(sfg == 1)
		#indqt = np.where(sfg == 0)
		self.table['sfg'] = sfg
	#def separate_nuv_r(self):


	def get_sf_qt_mass_redshift_bins(self, znodes, mnodes):
		self.id_z_ms = {}
		for iz in range(len(znodes[:-1])):
			for jm in range(len(mnodes[:-1])):
				#ind_mz_sf =( (self.table.sfg == 1) & (self.table.z_peak >= znodes[iz]) & (self.table.z_peak < znodes[iz+1]) & 
				#	(10**self.table.LMASS >= 10**mnodes[jm]) & (10**self.table.LMASS < 10**mnodes[jm+1]) ) 
				#ind_mz_qt =( (self.table.sfg == 0) & (self.table.z_peak >= znodes[iz]) & (self.table.z_peak < znodes[iz+1]) & 
				#	(10**self.table.LMASS >= 10**mnodes[jm]) & (10**self.table.LMASS < 10**mnodes[jm+1]) ) 
				ind_mz_sf =( (self.table.sfg == 1) & (self.table.z_peak >= np.min(znodes[iz:iz+2])) & (self.table.z_peak < np.max(znodes[iz:iz+2])) & 
					(10**self.table.LMASS >= 10**np.min(mnodes[jm:jm+2])) & (10**self.table.LMASS < 10**np.max(mnodes[jm:jm+2])) ) 
				ind_mz_qt =( (self.table.sfg == 0) & (self.table.z_peak >= np.min(znodes[iz:iz+2])) & (self.table.z_peak < np.max(znodes[iz:iz+2])) & 
					(10**self.table.LMASS >= 10**np.min(mnodes[jm:jm+2])) & (10**self.table.LMASS < 10**np.max(mnodes[jm:jm+2])) ) 

				#self.id_z_ms['z_'+str(znodes[iz])+'-'+str(znodes[iz+1])+'__m_'+str(mnodes[jm])+'-'+str(mnodes[jm+1])+'_sf'] = self.table.ID[ind_mz_sf].values 
				#self.id_z_ms['z_'+str(znodes[iz])+'-'+str(znodes[iz+1])+'__m_'+str(mnodes[jm])+'-'+str(mnodes[jm+1])+'_qt'] = self.table.ID[ind_mz_qt].values 
				#self.id_z_ms['z_'+str(znodes[iz]).replace('.','p')+'_'+str(znodes[iz+1]).replace('.','p')+'__m_'+str(mnodes[jm]).replace('.','p')+'_'+str(mnodes[jm+1]).replace('.','p')+'_sf'] = self.table.ID[ind_mz_sf].values 
				#self.id_z_ms['z_'+str(znodes[iz]).replace('.','p')+'_'+str(znodes[iz+1]).replace('.','p')+'__m_'+str(mnodes[jm]).replace('.','p')+'_'+str(mnodes[jm+1]).replace('.','p')+'_qt'] = self.table.ID[ind_mz_qt].values 
				self.id_z_ms['z_'+clean_args(str(round(znodes[iz],3)))+'_'+clean_args(str(round(znodes[iz+1],3)))+'__m_'+clean_args(str(round(mnodes[jm],3)))+'_'+clean_args(str(round(mnodes[jm+1],3)))+'_sf'] = self.table.ID[ind_mz_sf].values 
				self.id_z_ms['z_'+clean_args(str(round(znodes[iz],3)))+'_'+clean_args(str(round(znodes[iz+1],3)))+'__m_'+clean_args(str(round(mnodes[jm],3)))+'_'+clean_args(str(round(mnodes[jm+1],3)))+'_qt'] = self.table.ID[ind_mz_qt].values 

	def get_sf_qt_mass_lookback_time_bins(self, tnodes, mnodes):
		self.id_lookt_mass = {}
		age_universe = cosmo.age(0).value # 13.797617455819209 Gyr
		znodes = np.array([z_at_value(cosmo.age,(age_universe - i) * u.Gyr) for i in tnodes])

		for iz in range(len(znodes[:-1])):
			for jm in range(len(mnodes[:-1])):
				ind_mt_sf =( (self.table.sfg == 1) & (self.table.z_peak >= np.min(znodes[iz:iz+2])) & (self.table.z_peak < np.max(znodes[iz:iz+2])) & 
					(10**self.table.LMASS >= 10**np.min(mnodes[jm:jm+2])) & (10**self.table.LMASS < 10**np.max(mnodes[jm:jm+2])) ) 
				ind_mt_qt =( (self.table.sfg == 0) & (self.table.z_peak >= np.min(znodes[iz:iz+2])) & (self.table.z_peak < np.max(znodes[iz:iz+2])) & 
					(10**self.table.LMASS >= 10**np.min(mnodes[jm:jm+2])) & (10**self.table.LMASS < 10**np.max(mnodes[jm:jm+2])) ) 

				self.id_lookt_mass['lookt_'+clean_args(str(round(tnodes[iz],3)))+'_'+clean_args(str(round(tnodes[iz+1],3)))+'__m_'+clean_args(str(round(mnodes[jm],3)))+'_'+clean_args(str(round(mnodes[jm+1],3)))+'_sf'] = self.table.ID[ind_mt_sf].values 
				self.id_lookt_mass['lookt_'+clean_args(str(round(tnodes[iz],3)))+'_'+clean_args(str(round(tnodes[iz+1],3)))+'__m_'+clean_args(str(round(mnodes[jm],3)))+'_'+clean_args(str(round(mnodes[jm+1],3)))+'_qt'] = self.table.ID[ind_mt_qt].values 

	def get_sf_qt_agn_mass_redshift_bins(self, znodes, mnodes):
		self.id_z_ms = {}
		for iz in range(len(znodes[:-1])):
			for jm in range(len(mnodes[:-1])):
				ind_mz_sf =( (self.table.sfg == 1) & (self.table.z_peak >= np.min(znodes[iz:iz+2])) & (self.table.z_peak < np.max(znodes[iz:iz+2])) & 
					(10**self.table.LMASS >= 10**np.min(mnodes[jm:jm+2])) & (10**self.table.LMASS < 10**np.max(mnodes[jm:jm+2])) ) 
				ind_mz_qt =( (self.table.sfg == 0) & (self.table.z_peak >= np.min(znodes[iz:iz+2])) & (self.table.z_peak < np.max(znodes[iz:iz+2])) & 
					(10**self.table.LMASS >= 10**np.min(mnodes[jm:jm+2])) & (10**self.table.LMASS < 10**np.max(mnodes[jm:jm+2])) ) 
				ind_mz_agn =( (self.table.sfg == 2) & (self.table.z_peak >= np.min(znodes[iz:iz+2])) & (self.table.z_peak < np.max(znodes[iz:iz+2])) & 
					(10**self.table.LMASS >= 10**np.min(mnodes[jm:jm+2])) & (10**self.table.LMASS < 10**np.max(mnodes[jm:jm+2])) ) 

				self.id_z_ms['z_'+clean_args(str(round(znodes[iz],3)))+'_'+clean_args(str(round(znodes[iz+1],3)))+'__m_'+clean_args(str(round(mnodes[jm],3)))+'_'+clean_args(str(round(mnodes[jm+1],3)))+'_sf'] = self.table.ID[ind_mz_sf].values 
				self.id_z_ms['z_'+clean_args(str(round(znodes[iz],3)))+'_'+clean_args(str(round(znodes[iz+1],3)))+'__m_'+clean_args(str(round(mnodes[jm],3)))+'_'+clean_args(str(round(mnodes[jm+1],3)))+'_qt'] = self.table.ID[ind_mz_qt].values 
				self.id_z_ms['z_'+clean_args(str(round(znodes[iz],3)))+'_'+clean_args(str(round(znodes[iz+1],3)))+'__m_'+clean_args(str(round(mnodes[jm],3)))+'_'+clean_args(str(round(mnodes[jm+1],3)))+'_agn'] = self.table.ID[ind_mz_agn].values 

	def get_general_redshift_bins(self, znodes, mnodes, sfg = 1, suffx = '', Fcut = 25, Ahat = 1.0, initialize_pop = False):
		if initialize_pop == True: self.id_z_ms = {}
		for iz in range(len(znodes[:-1])):
			for jm in range(len(mnodes[:-1])):
				ind_mz =( (self.table.sfg == 1) & (self.table.z_peak >= np.min(znodes[iz:iz+2])) & (self.table.z_peak < np.max(znodes[iz:iz+2])) & 
					(10**self.table.LMASS >= 10**np.min(mnodes[jm:jm+2])) & (10**self.table.LMASS < 10**np.max(mnodes[jm:jm+2])) ) 

				self.id_z_ms['z_'+clean_args(str(round(znodes[iz],3)))+'_'+clean_args(str(round(znodes[iz+1],3)))+'__m_'+clean_args(str(round(mnodes[jm],3)))+'_'+clean_args(str(round(mnodes[jm+1],3)))+suffx] = self.table.ID[ind_mz].values 

	def get_mass_redshift_bins(self, znodes, mnodes, sfg = 1, pop_suffix = '', initialize_pop = False):
		if initialize_pop == True: self.id_z_ms_pop = {}
		for iz in range(len(znodes[:-1])):
			for jm in range(len(mnodes[:-1])):
				ind_mz =( (self.table.sfg == sfg) & (self.table.z_peak >= np.min(znodes[iz:iz+2])) & (self.table.z_peak < np.max(znodes[iz:iz+2])) & 
					(10**self.table.LMASS >= 10**np.min(mnodes[jm:jm+2])) & (10**self.table.LMASS < 10**np.max(mnodes[jm:jm+2])) ) 

				self.id_z_ms_pop['z_'+clean_args(str(round(znodes[iz],3)))+'_'+clean_args(str(round(znodes[iz+1],3)))+'__m_'+clean_args(str(round(mnodes[jm],3)))+'_'+clean_args(str(round(mnodes[jm+1],3)))+pop_suffix] = self.table.ID[ind_mz].values 

	def get_criteria_specific_redshift_bins(self, znodes, mnodes, sfg = 1, criteria = '', crange = [1.0], initialize_pop = False):
		pop = ['qt','sf']
		nc = len(crange)
		if initialize_pop == True: self.id_crit = {}

		for iz in range(len(znodes[:-1])):
			for jm in range(len(mnodes[:-1])):
				if nc > 1:
					for kc in range(len(crange[:-1])):
						ind_crit =( (self.table.sfg == sfg) & (self.table.z_peak >= np.min(znodes[iz:iz+2])) & (self.table.z_peak < np.max(znodes[iz:iz+2])) & 
							(10**self.table.LMASS >= 10**np.min(mnodes[jm:jm+2])) & (10**self.table.LMASS < 10**np.max(mnodes[jm:jm+2])) & 
							(clean_nans(self.table[criteria]) >= crange[kc]) & (clean_nans(self.table[criteria]) < crange[kc+1]) ) 

						arg = 'z_'+str(round(znodes[iz],3))+'_'+str(round(znodes[iz+1],3))+'__m_'+str(round(mnodes[jm],3))+'_'+str(round(mnodes[jm+1],3))+'__'+criteria+'_'+str(round(crange[kc],2))+'_'+str(round(crange[kc+1],2))+'_'+pop[sfg]
						self.id_crit[clean_args(arg)] = self.table.ID[ind_crit].values 
				else:
					#above and below no?
					ind_above =( (self.table.sfg == sfg) & (self.table.z_peak >= np.min(znodes[iz:iz+2])) & (self.table.z_peak < np.max(znodes[iz:iz+2])) & 
						(10**self.table.LMASS >= 10**np.min(mnodes[jm:jm+2])) & (10**self.table.LMASS < 10**np.max(mnodes[jm:jm+2])) & 
						(clean_nans(self.table[criteria]) >= crange[0]) ) 
					ind_below =( (self.table.sfg == sfg) & (self.table.z_peak >= np.min(znodes[iz:iz+2])) & (self.table.z_peak < np.max(znodes[iz:iz+2])) & 
						(10**self.table.LMASS >= 10**np.min(mnodes[jm:jm+2])) & (10**self.table.LMASS < 10**np.max(mnodes[jm:jm+2])) & 
						(clean_nans(self.table[criteria]) < crange[0]) ) 

					arg = 'z_'+str(round(znodes[iz],3))+'_'+str(round(znodes[iz+1],3))+'__m_'+str(round(mnodes[jm],3))+'_'+str(round(mnodes[jm+1],3))+'__'+criteria+'_ge_'+str(round(crange[0],2))+'_'+pop[sfg]
					self.id_crit[clean_args(arg)] = self.table.ID[ind_above].values 
					arg = 'z_'+str(round(znodes[iz],3))+'_'+str(round(znodes[iz+1],3))+'__m_'+str(round(mnodes[jm],3))+'_'+str(round(mnodes[jm+1],3))+'__'+criteria+'_lt_'+str(round(crange[0],2))+'_'+pop[sfg]
					self.id_crit[clean_args(arg)] = self.table.ID[ind_below].values 


	def get_parent_child_redshift_bins(self,znodes):
		self.id_z_sed = {}
		for ch in self.table.parent.unique():
			for iz in range(len(znodes[:-1])):
				self.id_z_sed['z_'+clean_args(str(znodes[iz]))+'_'+clean_args(str(znodes[iz+1]))+'__sed'+str(ch)] = self.table.ID[ (self.table.parent == ch) & (self.table.z_peak >= znodes[iz]) & (self.table.z_peak < znodes[iz+1]) ].values 

	def get_parent_child_bins(self):
		self.id_children = {}
		for ch in self.table.parent.unique():
			self.id_children['sed'+str(ch)] = self.table.ID[self.table.parent == ch].values 

	def subset_positions(self,radec_ids):
		''' This positions function is very general.  
			User supplies IDs dictionary, function returns RA/DEC dictionaries with the same keys'''
		#self.ra_dec = {}
		ra_dec = {}
		#ra = {}
		#dec = {}
		#pdb.set_trace()
		for k in radec_ids.keys():
			ra  = self.table.ra[self.table.ID.isin(radec_ids[k])].values
			dec = self.table.dec[self.table.ID.isin(radec_ids[k])].values
			#self.ra_dec[k] = [ra,dec] 
			#ra[k]  = ra
			#dec[k] = dec
			ra_dec[k] = [ra,dec]
		return ra_dec





