# -*- coding: UTF-8 -*-
# Copyright (C) 2016 Huang MaChi at Chongqing University
# of Posts and Telecommunications, Chongqing, China.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import argparse
import re
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties
chinese_font = FontProperties(fname='/usr/share/matplotlib/mpl-data/fonts/ttf/simhei.ttf')


parser = argparse.ArgumentParser(description="Plot BFlows experiments' results")
parser.add_argument('--k', dest='k', type=int, default=4, choices=[4, 8], help="Switch fanout number")
parser.add_argument('--duration', dest='duration', type=int, default=60, help="Duration (sec) for each iperf traffic generation")
parser.add_argument('--dir', dest='out_dir', help="Directory to store outputs")
parser.add_argument('--fnum', dest='flows_num_per_host', type=int, default=1, help="Number of iperf flows per host")
args = parser.parse_args()


def read_file_1(file_name, delim=','):
	"""
		Read the bwmng.txt file.
	"""
	read_file = open(file_name, 'r')
	lines = read_file.xreadlines()
	lines_list = []
	for line in lines:
		line_list = line.strip().split(delim)
		lines_list.append(line_list)
	read_file.close()

	# Remove the last second's statistics, because they are mostly not intact.
	last_second = lines_list[-1][0]
	_lines_list = lines_list[:]
	for line in _lines_list:
		if line[0] == last_second:
			lines_list.remove(line)

	return lines_list

def read_file_2(file_name):
	"""
		Read the first_packets.txt and successive_packets.txt file.
	"""
	read_file = open(file_name, 'r')
	lines = read_file.xreadlines()
	lines_list = []
	for line in lines:
		if line.startswith('rtt') or line.endswith('ms\n'):
			lines_list.append(line)
	read_file.close()
	return lines_list

def calculate_average(value_list):
	average_value = sum(map(float, value_list)) / len(value_list)
	return average_value

def get_throughput(throughput, traffic, app, input_file):
	"""
		csv output format:
		(Type rate)
		unix_timestamp;iface_name;bytes_out/s;bytes_in/s;bytes_total/s;bytes_in;bytes_out;packets_out/s;packets_in/s;packets_total/s;packets_in;packets_out;errors_out/s;errors_in/s;errors_in;errors_out\n
		(Type svg, sum, max)
		unix timestamp;iface_name;bytes_out;bytes_in;bytes_total;packets_out;packets_in;packets_total;errors_out;errors_in\n
		The bwm-ng mode used is 'rate'.

		throughput = {
						'random1':
						{
							'realtime_bisection_bw': {'BFlows':{0:x, 1:x, ..}, 'ECMP':{0:x, 1:x, ..}, ...},
							'realtime_throughput': {'BFlows':{0:x, 1:x, ..}, 'ECMP':{0:x, 1:x, ..}, ...},
							'accumulated_throughput': {'BFlows':{0:x, 1:x, ..}, 'ECMP':{0:x, 1:x, ..}, ...},
							'normalized_total_throughput': {'BFlows':x%, 'ECMP':x%, ...}
						},
						'random2':
						{
							'realtime_bisection_bw': {'BFlows':{0:x, 1:x, ..}, 'ECMP':{0:x, 1:x, ..}, ...},
							'realtime_throughput': {'BFlows':{0:x, 1:x, ..}, 'ECMP':{0:x, 1:x, ..}, ...},
							'accumulated_throughput': {'BFlows':{0:x, 1:x, ..}, 'ECMP':{0:x, 1:x, ..}, ...},
							'normalized_total_throughput': {'BFlows':x%, 'ECMP':x%, ...}
						},
						...
					}
	"""
	full_bisection_bw = 10.0 * (args.k ** 3 / 4)   # (unit: Mbit/s)
	lines_list = read_file_1(input_file)
	first_second = int(lines_list[0][0])
	column_bytes_out_rate = 2   # bytes_out/s
	column_bytes_out = 6   # bytes_out

	if app == 'NonBlocking':
		switch = '1001'
	elif app in ['ECMP', 'Hedera', 'PureSDN', 'BFlows']:
		switch = '3[0-9][0-9][0-9]'
	else:
		pass
	sw = re.compile(switch)

	if not throughput.has_key(traffic):
		throughput[traffic] = {}

	if not throughput[traffic].has_key('realtime_bisection_bw'):
		throughput[traffic]['realtime_bisection_bw'] = {}
	if not throughput[traffic].has_key('realtime_throughput'):
		throughput[traffic]['realtime_throughput'] = {}
	if not throughput[traffic].has_key('accumulated_throughput'):
		throughput[traffic]['accumulated_throughput'] = {}
	if not throughput[traffic].has_key('normalized_total_throughput'):
		throughput[traffic]['normalized_total_throughput'] = {}

	if not throughput[traffic]['realtime_bisection_bw'].has_key(app):
		throughput[traffic]['realtime_bisection_bw'][app] = {}
	if not throughput[traffic]['realtime_throughput'].has_key(app):
		throughput[traffic]['realtime_throughput'][app] = {}
	if not throughput[traffic]['accumulated_throughput'].has_key(app):
		throughput[traffic]['accumulated_throughput'][app] = {}
	if not throughput[traffic]['normalized_total_throughput'].has_key(app):
		throughput[traffic]['normalized_total_throughput'][app] = 0

	for i in xrange(args.duration + 1):
		if not throughput[traffic]['realtime_bisection_bw'][app].has_key(i):
			throughput[traffic]['realtime_bisection_bw'][app][i] = 0
		if not throughput[traffic]['realtime_throughput'][app].has_key(i):
			throughput[traffic]['realtime_throughput'][app][i] = 0
		if not throughput[traffic]['accumulated_throughput'][app].has_key(i):
			throughput[traffic]['accumulated_throughput'][app][i] = 0

	for row in lines_list:
		iface_name = row[1]
		if iface_name not in ['total', 'lo', 'eth0', 'enp0s3', 'enp0s8', 'docker0']:
			if switch == '3[0-9][0-9][0-9]':
				if sw.match(iface_name):
					if int(iface_name[-1]) > args.k / 2:   # Choose down-going interfaces only.
						if (int(row[0]) - first_second) <= args.duration:   # Take the good values only.
							throughput[traffic]['realtime_bisection_bw'][app][int(row[0]) - first_second] += float(row[column_bytes_out_rate]) * 8.0 / (10 ** 6)   # Mbit/s
							throughput[traffic]['realtime_throughput'][app][int(row[0]) - first_second] += float(row[column_bytes_out]) * 8.0 / (10 ** 6)   # Mbit
			elif switch == '1001':   # Choose all the interfaces. (For NonBlocking Topo only)
				if sw.match(iface_name):
					if (int(row[0]) - first_second) <= args.duration:
						throughput[traffic]['realtime_bisection_bw'][app][int(row[0]) - first_second] += float(row[column_bytes_out_rate]) * 8.0 / (10 ** 6)   # Mbit/s
						throughput[traffic]['realtime_throughput'][app][int(row[0]) - first_second] += float(row[column_bytes_out]) * 8.0 / (10 ** 6)   # Mbit
			else:
				pass

	for i in xrange(args.duration + 1):
		for j in xrange(i+1):
			throughput[traffic]['accumulated_throughput'][app][i] += throughput[traffic]['realtime_throughput'][app][j]   # Mbit

	throughput[traffic]['normalized_total_throughput'][app] = throughput[traffic]['accumulated_throughput'][app][args.duration] / (full_bisection_bw * args.duration)   # percentage

	return throughput

def get_value_list_1(throughput, traffic, item, app):
	"""
		Get the values from the "throughput" data structure.
	"""
	value_list = []
	for i in xrange(args.duration + 1):
		value_list.append(throughput[traffic][item][app][i])
	return value_list

def get_average_bisection_bw(throughput, traffics, app):
	value_list = []
	complete_list = []
	for traffic in traffics:
		complete_list.append(throughput[traffic]['accumulated_throughput'][app][args.duration] / float(args.duration))
	for i in xrange(9):
		value_list.append(calculate_average(complete_list[(i * 20): (i * 20 + 20)]))
	return value_list

def get_value_list_2(value_dict, traffics, item, app):
	"""
		Get the values from the  data structure.
	"""
	value_list = []
	complete_list = []
	for traffic in traffics:
		complete_list.append(value_dict[traffic][item][app])
	for i in xrange(9):
		value_list.append(calculate_average(complete_list[(i * 20): (i * 20 + 20)]))
	return value_list

def get_utilization(utilization, traffic, app, input_file):
	"""
		Get link utilization and link bandwidth utilization.
	"""
	lines_list = read_file_1(input_file)
	first_second = int(lines_list[0][0])
	column_packets_out = 11   # packets_out
	column_packets_in = 10   # packets_in
	column_bytes_out = 6   # bytes_out
	column_bytes_in = 5   # bytes_in

	if not utilization.has_key(traffic):
		utilization[traffic] = {}
	if not utilization[traffic].has_key(app):
		utilization[traffic][app] = {}

	for row in lines_list:
		iface_name = row[1]
		if iface_name.startswith('1'):
			if (int(row[0]) - first_second) <= args.duration:   # Take the good values only.
				if not utilization[traffic][app].has_key(iface_name):
					utilization[traffic][app][iface_name] = {'LU_out':0, 'LU_in':0, 'LBU_out':0, 'LBU_in':0}
				# if int(row[11]) > 2:
				if row[6] not in ['0', '60', '120']:
					utilization[traffic][app][iface_name]['LU_out'] = 1
				# if int(row[10]) > 2:
				if row[5] not in ['0', '60', '120']:
					utilization[traffic][app][iface_name]['LU_in'] = 1
				utilization[traffic][app][iface_name]['LBU_out'] += int(row[6])
				utilization[traffic][app][iface_name]['LBU_in'] += int(row[5])
		elif iface_name.startswith('2'):
			if int(iface_name[-1]) > args.k / 2:   # Choose down-going interfaces only.
				if (int(row[0]) - first_second) <= args.duration:   # Take the good values only.
					if not utilization[traffic][app].has_key(iface_name):
						utilization[traffic][app][iface_name] = {'LU_out':0, 'LU_in':0, 'LBU_out':0, 'LBU_in':0}
					# if int(row[11]) > 2:
					if row[6] not in ['0', '60', '120']:
						utilization[traffic][app][iface_name]['LU_out'] = 1
					# if int(row[10]) > 2:
					if row[5] not in['0', '60', '120']:
						utilization[traffic][app][iface_name]['LU_in'] = 1
					utilization[traffic][app][iface_name]['LBU_out'] += int(row[6])
					utilization[traffic][app][iface_name]['LBU_in'] += int(row[5])
		else:
			pass

	return utilization

def get_link_utilization_ratio(utilization, traffics, app):
	value_list = []
	num_list = []
	complete_list = []
	average_list = []
	for traffic in traffics:
		num = 0
		for interface in utilization[traffic][app].keys():
			if utilization[traffic][app][interface]['LU_out'] == 1:
				num += 1
			if utilization[traffic][app][interface]['LU_in'] == 1:
				num += 1
		num_list.append(num)
		complete_list.append(float(num) / (len(utilization[traffic][app].keys()) * 2))
	for i in xrange(9):
		value_list.append(calculate_average(complete_list[(i * 20): (i * 20 + 20)]))
	for i in xrange(9):
		average_list.append(calculate_average(num_list[(i * 20): (i * 20 + 20)]))
	# print "average_list:", average_list
	return value_list

def get_value_list_3(utilization, some_traffics, app):
	"""
		Get link bandwidth utilization ratio.
	"""
	value_list = []
	link_bandwidth_utilization = {}
	utilization_list = []
	for i in np.linspace(0, 1, 101):
		link_bandwidth_utilization[i] = 0

	for traffic in some_traffics:
		for interface in utilization[traffic][app].keys():
			ratio_out = float(utilization[traffic][app][interface]['LBU_out'] * 8) / (10 * (10 ** 6) * args.duration)
			ratio_in = float(utilization[traffic][app][interface]['LBU_in'] * 8) / (10 * (10 ** 6) * args.duration)
			utilization_list.append(ratio_out)
			utilization_list.append(ratio_in)

	for ratio in utilization_list:
		for seq in link_bandwidth_utilization.keys():
			if ratio <= seq:
				link_bandwidth_utilization[seq] += 1

	for seq in link_bandwidth_utilization.keys():
		link_bandwidth_utilization[seq] = float(link_bandwidth_utilization[seq]) / len(utilization_list)

	for seq in sorted(link_bandwidth_utilization.keys()):
		value_list.append(link_bandwidth_utilization[seq])

	return value_list

def plot_results():
	"""
		Plot the results:
		1. Plot average bisection bandwidth
		2. Plot normalized total throughput
		3. Plot link utilization ratio
		4. Plot link bandwidth utilization ratio

		throughput = {
						'random1':
						{
							'realtime_bisection_bw': {'BFlows':{0:x, 1:x, ..}, 'ECMP':{0:x, 1:x, ..}, ...},
							'realtime_throughput': {'BFlows':{0:x, 1:x, ..}, 'ECMP':{0:x, 1:x, ..}, ...},
							'accumulated_throughput': {'BFlows':{0:x, 1:x, ..}, 'ECMP':{0:x, 1:x, ..}, ...},
							'normalized_total_throughput': {'BFlows':x%, 'ECMP':x%, ...}
						},
						'random2':
						{
							'realtime_bisection_bw': {'BFlows':{0:x, 1:x, ..}, 'ECMP':{0:x, 1:x, ..}, ...},
							'realtime_throughput': {'BFlows':{0:x, 1:x, ..}, 'ECMP':{0:x, 1:x, ..}, ...},
							'accumulated_throughput': {'BFlows':{0:x, 1:x, ..}, 'ECMP':{0:x, 1:x, ..}, ...},
							'normalized_total_throughput': {'BFlows':x%, 'ECMP':x%, ...}
						},
						...
					}
	"""
	full_bisection_bw = 10.0 * (args.k ** 3 / 4)   # (unit: Mbit/s)
	utmost_throughput = full_bisection_bw * args.duration
	_traffics = "random1 random2 random3 random4 random5 random6 random7 random8 random9 random10 random11 random12 random13 random14 random15 random16 random17 random18 random19 random20 stag1_0.1_0.2 stag2_0.1_0.2 stag3_0.1_0.2 stag4_0.1_0.2 stag5_0.1_0.2 stag6_0.1_0.2 stag7_0.1_0.2 stag8_0.1_0.2 stag9_0.1_0.2 stag10_0.1_0.2 stag11_0.1_0.2 stag12_0.1_0.2 stag13_0.1_0.2 stag14_0.1_0.2 stag15_0.1_0.2 stag16_0.1_0.2 stag17_0.1_0.2 stag18_0.1_0.2 stag19_0.1_0.2 stag20_0.1_0.2 stag1_0.2_0.3 stag2_0.2_0.3 stag3_0.2_0.3 stag4_0.2_0.3 stag5_0.2_0.3 stag6_0.2_0.3 stag7_0.2_0.3 stag8_0.2_0.3 stag9_0.2_0.3 stag10_0.2_0.3 stag11_0.2_0.3 stag12_0.2_0.3 stag13_0.2_0.3 stag14_0.2_0.3 stag15_0.2_0.3 stag16_0.2_0.3 stag17_0.2_0.3 stag18_0.2_0.3 stag19_0.2_0.3 stag20_0.2_0.3 stag1_0.3_0.3 stag2_0.3_0.3 stag3_0.3_0.3 stag4_0.3_0.3 stag5_0.3_0.3 stag6_0.3_0.3 stag7_0.3_0.3 stag8_0.3_0.3 stag9_0.3_0.3 stag10_0.3_0.3 stag11_0.3_0.3 stag12_0.3_0.3 stag13_0.3_0.3 stag14_0.3_0.3 stag15_0.3_0.3 stag16_0.3_0.3 stag17_0.3_0.3 stag18_0.3_0.3 stag19_0.3_0.3 stag20_0.3_0.3 stag1_0.4_0.3 stag2_0.4_0.3 stag3_0.4_0.3 stag4_0.4_0.3 stag5_0.4_0.3 stag6_0.4_0.3 stag7_0.4_0.3 stag8_0.4_0.3 stag9_0.4_0.3 stag10_0.4_0.3 stag11_0.4_0.3 stag12_0.4_0.3 stag13_0.4_0.3 stag14_0.4_0.3 stag15_0.4_0.3 stag16_0.4_0.3 stag17_0.4_0.3 stag18_0.4_0.3 stag19_0.4_0.3 stag20_0.4_0.3 stag1_0.5_0.3 stag2_0.5_0.3 stag3_0.5_0.3 stag4_0.5_0.3 stag5_0.5_0.3 stag6_0.5_0.3 stag7_0.5_0.3 stag8_0.5_0.3 stag9_0.5_0.3 stag10_0.5_0.3 stag11_0.5_0.3 stag12_0.5_0.3 stag13_0.5_0.3 stag14_0.5_0.3 stag15_0.5_0.3 stag16_0.5_0.3 stag17_0.5_0.3 stag18_0.5_0.3 stag19_0.5_0.3 stag20_0.5_0.3 stag1_0.6_0.2 stag2_0.6_0.2 stag3_0.6_0.2 stag4_0.6_0.2 stag5_0.6_0.2 stag6_0.6_0.2 stag7_0.6_0.2 stag8_0.6_0.2 stag9_0.6_0.2 stag10_0.6_0.2 stag11_0.6_0.2 stag12_0.6_0.2 stag13_0.6_0.2 stag14_0.6_0.2 stag15_0.6_0.2 stag16_0.6_0.2 stag17_0.6_0.2 stag18_0.6_0.2 stag19_0.6_0.2 stag20_0.6_0.2 stag1_0.7_0.2 stag2_0.7_0.2 stag3_0.7_0.2 stag4_0.7_0.2 stag5_0.7_0.2 stag6_0.7_0.2 stag7_0.7_0.2 stag8_0.7_0.2 stag9_0.7_0.2 stag10_0.7_0.2 stag11_0.7_0.2 stag12_0.7_0.2 stag13_0.7_0.2 stag14_0.7_0.2 stag15_0.7_0.2 stag16_0.7_0.2 stag17_0.7_0.2 stag18_0.7_0.2 stag19_0.7_0.2 stag20_0.7_0.2 stag1_0.8_0.1 stag2_0.8_0.1 stag3_0.8_0.1 stag4_0.8_0.1 stag5_0.8_0.1 stag6_0.8_0.1 stag7_0.8_0.1 stag8_0.8_0.1 stag9_0.8_0.1 stag10_0.8_0.1 stag11_0.8_0.1 stag12_0.8_0.1 stag13_0.8_0.1 stag14_0.8_0.1 stag15_0.8_0.1 stag16_0.8_0.1 stag17_0.8_0.1 stag18_0.8_0.1 stag19_0.8_0.1 stag20_0.8_0.1"
	traffics = _traffics.split(' ')
	traffics_brief = ['random', 'stag_0.1_0.2', 'stag_0.2_0.3', 'stag_0.3_0.3', 'stag_0.4_0.3', 'stag_0.5_0.3', 'stag_0.6_0.2', 'stag_0.7_0.2', 'stag_0.8_0.1']
	apps = ['BFlows', 'ECMP', 'PureSDN', 'Hedera', 'NonBlocking']
	throughput = {}
	utilization = {}

	for traffic in traffics:
		for app in apps:
			bwmng_file = args.out_dir + '/%s/%s/%s/bwmng.txt' % (args.flows_num_per_host, traffic, app)
			throughput = get_throughput(throughput, traffic, app, bwmng_file)
			utilization = get_utilization(utilization, traffic, app, bwmng_file)

	# 1. Plot average throughput.
	fig = plt.figure()
	fig.set_size_inches(10, 5)
	num_groups = len(traffics_brief)
	num_bar = len(apps)
	ECMP_value_list = get_average_bisection_bw(throughput, traffics, 'ECMP')
	Hedera_value_list = get_average_bisection_bw(throughput, traffics, 'Hedera')
	PureSDN_value_list = get_average_bisection_bw(throughput, traffics, 'PureSDN')
	BFlows_value_list = get_average_bisection_bw(throughput, traffics, 'BFlows')
	NonBlocking_value_list = get_average_bisection_bw(throughput, traffics, 'NonBlocking')
	# print "ECMP_value_list:", ECMP_value_list
	# print "Hedera_value_list:", Hedera_value_list
	# print "PureSDN_value_list:", PureSDN_value_list
	# print "BFlows_value_list:", BFlows_value_list
	index = np.arange(num_groups) + 0.15
	bar_width = 0.13
	plt.bar(index, ECMP_value_list, bar_width, color='b', label='ECMP')
	plt.bar(index + 1 * bar_width, Hedera_value_list, bar_width, color='y', label='Hedera')
	plt.bar(index + 2 * bar_width, PureSDN_value_list, bar_width, color='g', label='PureSDN')
	plt.bar(index + 3 * bar_width, BFlows_value_list, bar_width, color='r', label='BFlows')
	plt.bar(index + 4 * bar_width, NonBlocking_value_list, bar_width, color='k', label='NonBlocking')
	plt.xticks(index + num_bar / 2.0 * bar_width, traffics_brief, fontsize='small')
	plt.ylabel(u'平均吞吐率\n(Mbps)', fontsize='xx-large', fontproperties=chinese_font)
	plt.ylim(0, full_bisection_bw)
	plt.yticks(np.linspace(0, full_bisection_bw, 11))
	plt.legend(loc='upper right', ncol=len(apps), fontsize='small')
	plt.grid(axis='y')
	plt.tight_layout()
	plt.savefig(args.out_dir + '/%s-1.average_throughput.png' % args.flows_num_per_host)

	# 2. Plot normalized total throughput.
	item = 'normalized_total_throughput'
	fig = plt.figure()
	fig.set_size_inches(10, 5)
	num_groups = len(traffics_brief)
	num_bar = len(apps)
	ECMP_value_list = get_value_list_2(throughput, traffics, item, 'ECMP')
	Hedera_value_list = get_value_list_2(throughput, traffics, item, 'Hedera')
	PureSDN_value_list = get_value_list_2(throughput, traffics, item, 'PureSDN')
	BFlows_value_list = get_value_list_2(throughput, traffics, item, 'BFlows')
	NonBlocking_value_list = get_value_list_2(throughput, traffics, item, 'NonBlocking')
	index = np.arange(num_groups) + 0.15
	bar_width = 0.13
	plt.bar(index, ECMP_value_list, bar_width, color='b', label='ECMP')
	plt.bar(index + 1 * bar_width, Hedera_value_list, bar_width, color='y', label='Hedera')
	plt.bar(index + 2 * bar_width, PureSDN_value_list, bar_width, color='g', label='PureSDN')
	plt.bar(index + 3 * bar_width, BFlows_value_list, bar_width, color='r', label='BFlows')
	plt.bar(index + 4 * bar_width, NonBlocking_value_list, bar_width, color='k', label='NonBlocking')
	plt.xticks(index + num_bar / 2.0 * bar_width, traffics_brief, fontsize='small')
	plt.ylabel(u'标准化总吞吐量\n', fontsize='xx-large', fontproperties=chinese_font)
	plt.ylim(0, 1)
	plt.yticks(np.linspace(0, 1, 11))
	plt.legend(loc='upper right', ncol=len(apps), fontsize='small')
	plt.grid(axis='y')
	plt.tight_layout()
	plt.savefig(args.out_dir + '/%s-2.normalized_total_throughput.png' % args.flows_num_per_host)

	# 3. Plot link utilization ratio.
	fig = plt.figure()
	fig.set_size_inches(10, 5)
	num_groups = len(traffics_brief)
	num_bar = len(apps) - 1
	ECMP_value_list = get_link_utilization_ratio(utilization, traffics, 'ECMP')
	BFlows_value_list = get_link_utilization_ratio(utilization, traffics, 'BFlows')
	PureSDN_value_list = get_link_utilization_ratio(utilization, traffics, 'PureSDN')
	Hedera_value_list = get_link_utilization_ratio(utilization, traffics, 'Hedera')
	index = np.arange(num_groups) + 0.15
	bar_width = 0.15
	plt.bar(index, ECMP_value_list, bar_width, color='b', label='ECMP')
	plt.bar(index + 1 * bar_width, BFlows_value_list, bar_width, color='r', label='BFlows')
	plt.bar(index + 2 * bar_width, PureSDN_value_list, bar_width, color='g', label='PureSDN')
	plt.bar(index + 3 * bar_width, Hedera_value_list, bar_width, color='y', label='Hedera')
	plt.xticks(index + num_bar / 2.0 * bar_width, traffics_brief, fontsize='small')
	plt.ylabel(u'链路利用率\n', fontsize='xx-large', fontproperties=chinese_font)
	plt.ylim(0, 1)
	plt.yticks(np.linspace(0, 1, 11))
	plt.legend(loc='upper right', ncol=len(apps)-1, fontsize='small')
	plt.grid(axis='y')
	plt.tight_layout()
	plt.savefig(args.out_dir + '/%s-3.link_utilization_ratio.png' % args.flows_num_per_host)

	# 4. Plot link bandwidth utilization ratio.
	fig = plt.figure()
	fig.set_size_inches(12, 20)
	num_subplot = len(traffics_brief)
	num_raw = 5
	num_column = 2
	NO_subplot = 1
	x = np.linspace(0, 1, 101)
	for i in xrange(len(traffics_brief)):
		plt.subplot(num_raw, num_column, NO_subplot)
		y1 = get_value_list_3(utilization, traffics[(i * 20): (i * 20 + 20)], 'ECMP')
		y2 = get_value_list_3(utilization, traffics[(i * 20): (i * 20 + 20)], 'Hedera')
		y3 = get_value_list_3(utilization, traffics[(i * 20): (i * 20 + 20)], 'PureSDN')
		y4 = get_value_list_3(utilization, traffics[(i * 20): (i * 20 + 20)], 'BFlows')
		# print "y1[10]:", y1[10]
		# print "y2[10]:", y2[10]
		# print "y3[10]:", y3[10]
		# print "y4[10]:", y4[10]
		plt.plot(x, y1, 'b-', linewidth=2, label="ECMP")
		plt.plot(x, y2, 'y-', linewidth=2, label="Hedera")
		plt.plot(x, y3, 'g-', linewidth=2, label="PureSDN")
		plt.plot(x, y4, 'r-', linewidth=2, label="BFlows")
		plt.title('%s' % traffics_brief[i], fontsize='xx-large')
		plt.xlabel(u'链路带宽利用率', fontsize='xx-large', fontproperties=chinese_font)
		plt.xlim(0, 1)
		plt.xticks(np.linspace(0, 1, 11))
		plt.ylabel(u'链路带宽利用率\n累积分布函数', fontsize='xx-large', fontproperties=chinese_font)
		plt.ylim(0, 1)
		plt.yticks(np.linspace(0, 1, 11))
		plt.legend(loc='lower right', fontsize='large')
		plt.grid(True)
		NO_subplot += 1
	plt.tight_layout()
	plt.savefig(args.out_dir + '/%s-4.link_bandwidth_utilization_ratio.png' % args.flows_num_per_host)


if __name__ == '__main__':
	plot_results()
