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
import random


parser = argparse.ArgumentParser(description="BFlows experiments")
parser.add_argument('--k', dest='k', type=int, default=4, choices=[4, 8], help="Switch fanout number")
parser.add_argument('--traffic', dest='traffic', default="stag_0.2_0.3", help="Traffic pattern to simulate")
parser.add_argument('--fnum', dest='flows_num_per_host', type=int, default=1, help="Number of iperf flows per host")
args = parser.parse_args()


def create_subnetList(num):
	"""
		Create the subnet list of the certain Pod.
	"""
	subnetList = []
	remainder = num % (args.k / 2)
	if args.k == 4:
		if remainder == 0:
			subnetList = [num-1, num]
		elif remainder == 1:
			subnetList = [num, num+1]
		else:
			pass
	elif args.k == 8:
		if remainder == 0:
			subnetList = [num-3, num-2, num-1, num]
		elif remainder == 1:
			subnetList = [num, num+1, num+2, num+3]
		elif remainder == 2:
			subnetList = [num-1, num, num+1, num+2]
		elif remainder == 3:
			subnetList = [num-2, num-1, num, num+1]
		else:
			pass
	else:
		pass
	return subnetList

def create_swList(num):
	"""
		Create the host list under the certain Edge switch.
		Note: Part of this function is the same with the create_subnetList( ).
	"""
	swList = []
	list_num = create_subnetList(num)
	for i in list_num:
		if i < 10:
			swList.append('h00' + str(i))
		elif i < 100:
			swList.append('h0' + str(i))
		else:
			swList.append('h' + str(i))
	return swList

def create_podList(num):
	"""
		Create the host list of the certain Pod.
	"""
	podList = []
	list_num = []
	host_num_per_pod = args.k ** 2 / 4
	quotient = (num - 1) / host_num_per_pod
	list_num = [i for i in range(host_num_per_pod * quotient + 1, host_num_per_pod * quotient + host_num_per_pod + 1)]

	for i in list_num:
		if i < 10:
			podList.append('h00' + str(i))
		elif i < 100:
			podList.append('h0' + str(i))
		else:
			podList.append('h' + str(i))
	return podList

def create_stag_peers(HostList, edge_prob, pod_prob, flows_num_per_host):
	"""
		Create staggered iperf peers to generate traffic.
	"""
	peers = []
	for host in HostList:
		num = int(host[1:])
		swList = create_swList(num)
		podList = create_podList(num)
		new_peers = []
		while len(new_peers) < flows_num_per_host:
			probability = random.random()
			if probability < edge_prob:
				peer = random.choice(swList)
				if (peer != host) and ((host, peer) not in new_peers):
					new_peers.append((host, peer))
			elif edge_prob <= probability < edge_prob + pod_prob:
				peer = random.choice(podList)
				if (peer not in swList) and ((host, peer) not in new_peers):
					new_peers.append((host, peer))
			else:
				peer = random.choice(HostList)
				if (peer not in podList) and ((host, peer) not in new_peers):
					new_peers.append((host, peer))
		peers.extend(new_peers)
	return peers

def create_random_peers(HostList, flows_num_per_host):
	"""
		Create random iperf peers to generate traffic.
	"""
	peers = []
	for host in HostList:
		for i in xrange(flows_num_per_host):
			peer = random.choice(HostList)
			while (peer == host or (host, peer) in peers):
				peer = random.choice(HostList)
			peers.append((host, peer))
	return peers

def create_hostlist(num):
	"""
		Create hosts list.
	"""
	hostlist = []
	for i in xrange(1, num+1):
		if i >= 100:
			PREFIX = "h"
		elif i >= 10:
			PREFIX = "h0"
		else:
			PREFIX = "h00"
		hostlist.append(PREFIX + str(i))
	return hostlist

def create_peers():
	"""
		Create iperf host peers and write to a file.
	"""
	host_num = args.k ** 3 /4
	HostList = create_hostlist(host_num)

	if args.traffic.startswith('stag'):
		edge_prob, pod_prob = map(float, args.traffic.split('_')[1:])
		flows_peers = create_stag_peers(HostList, edge_prob, pod_prob, args.flows_num_per_host)
	elif args.traffic.startswith('random'):
		flows_peers = create_random_peers(HostList, args.flows_num_per_host)
	else:
		pass

	# Shuffle the sequence of the flows_peers.
	random.shuffle(flows_peers)

	# Write flows_peers into a file for reuse.
	file_save = open('iperf_peers.py', 'w')
	file_save.write('iperf_peers=%s' % flows_peers)
	file_save.close()

if __name__ == '__main__':
	create_peers()
