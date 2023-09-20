# Copyright (C) 2016 Huang MaChi at Chongqing University
# of Posts and Telecommunications, China.
# Copyright (C) 2016 Li Cheng at Beijing University of Posts
# and Telecommunications. www.muzixing.com
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

from mininet.net import Mininet
from mininet.node import Controller, RemoteController
from mininet.cli import CLI
from mininet.log import setLogLevel
from mininet.link import Link, Intf, TCLink
from mininet.topo import Topo

import os
import logging
import argparse
import time
import signal
from subprocess import Popen
from multiprocessing import Process

import sys
parentdir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, parentdir)
import iperf_peers


parser = argparse.ArgumentParser(description="NonBlocking application")
parser.add_argument('--k', dest='k', type=int, default=4, choices=[4, 8], help="Switch fanout number")
parser.add_argument('--duration', dest='duration', type=int, default=60, help="Duration (sec) for each iperf traffic generation")
parser.add_argument('--dir', dest='output_dir', help="Directory to store outputs")
parser.add_argument('--cpu', dest='cpu', type=float, default=1.0, help='Total CPU to allocate to hosts')
args = parser.parse_args()


class NonBlocking(Topo):
	"""
		Class of NonBlocking Topology.
	"""
	CoreSwitchList = []
	HostList = []

	def __init__(self, k):
		self.pod = k
		self.iCoreLayerSwitch = 1
		self.iHost = k**3/4

		# Topo initiation
		Topo.__init__(self)

	def createNodes(self):
		self.createCoreLayerSwitch(self.iCoreLayerSwitch)
		self.createHost(self.iHost)

	def _addSwitch(self, number, level, switch_list):
		"""
			Create switches.
		"""
		for i in xrange(1, number+1):
			PREFIX = str(level) + "00"
			if i >= 10:
				PREFIX = str(level) + "0"
			switch_list.append(self.addSwitch(PREFIX + str(i)))

	def createCoreLayerSwitch(self, NUMBER):
		self._addSwitch(NUMBER, 1, self.CoreSwitchList)

	def createHost(self, NUMBER):
		"""
			Create hosts.
		"""
		for i in xrange(1, NUMBER+1):
			if i >= 100:
				PREFIX = "h"
			elif i >= 10:
				PREFIX = "h0"
			else:
				PREFIX = "h00"
			self.HostList.append(self.addHost(PREFIX + str(i), cpu=args.cpu/float(NUMBER)))

	def createLinks(self, bw_h2c=10):
		"""
			Add links between switch and hosts.
		"""
		for sw in self.CoreSwitchList:
			for host in self.HostList:
				self.addLink(sw, host, bw=bw_h2c, max_queue_size=1000)   # use_htb=False

	def set_ovs_protocol_13(self):
		"""
			Set the OpenFlow version for switches.
		"""
		self._set_ovs_protocol_13(self.CoreSwitchList)

	def _set_ovs_protocol_13(self, sw_list):
		for sw in sw_list:
			cmd = "sudo ovs-vsctl set bridge %s protocols=OpenFlow13" % sw
			os.system(cmd)


def set_host_ip(net, topo):
	hostlist = []
	for k in xrange(len(topo.HostList)):
		hostlist.append(net.get(topo.HostList[k]))
	i = 1
	for host in hostlist:
		host.setIP("10.0.0.%d" % i)
		i += 1

def install_proactive(net, topo):
	"""
		Install proactive flow entries for the switch.
	"""
	for sw in topo.CoreSwitchList:
		for i in xrange(1, topo.iHost + 1):
			cmd = "ovs-ofctl add-flow %s -O OpenFlow13 \
				'table=0,idle_timeout=0,hard_timeout=0,priority=40,arp, \
				nw_dst=10.0.0.%d,actions=output:%d'" % (sw, i, i)
			os.system(cmd)
			cmd = "ovs-ofctl add-flow %s -O OpenFlow13 \
				'table=0,idle_timeout=0,hard_timeout=0,priority=40,ip, \
				nw_dst=10.0.0.%d,actions=output:%d'" % (sw, i, i)
			os.system(cmd)

def monitor_devs_ng(fname="./txrate.txt", interval_sec=0.1):
	"""
		Use bwm-ng tool to collect interface transmit rate statistics.
		bwm-ng Mode: rate;
		interval time: 1s.
	"""
	cmd = "sleep 1; bwm-ng -t %s -o csv -u bits -T rate -C ',' > %s" %  (interval_sec * 1000, fname)
	Popen(cmd, shell=True).wait()

def traffic_generation(net, topo, flows_peers):
	"""
		Generate traffics and test the performance of the network.
	"""
	# 1. Start iperf. (Elephant flows)
	# Start the servers.
	serversList = set([peer[1] for peer in flows_peers])
	for server in serversList:
		# filename = server[1:]
		server = net.get(server)
		# server.cmd("iperf -s > %s/%s &" % (args.output_dir, 'server'+filename+'.txt'))
		server.cmd("iperf -s > /dev/null &" )   # Its statistics is useless, just throw away.

	time.sleep(3)

	# Start the clients.
	for src, dest in flows_peers:
		server = net.get(dest)
		client = net.get(src)
		# filename = src[1:]
		# client.cmd("iperf -c %s -t %d > %s/%s &" % (server.IP(), args.duration, args.output_dir, 'client'+filename+'.txt'))
		client.cmd("iperf -c %s -t %d > /dev/null &" % (server.IP(), 1990))   # Its statistics is useless, just throw away. 1990 just means a great number.
		time.sleep(2)

	# Wait for the traffic to become stable.
	time.sleep(10)

	# 2. Start bwm-ng to monitor throughput.
	monitor = Process(target = monitor_devs_ng, args = ('%s/bwmng.txt' % args.output_dir, 1.0))
	monitor.start()

	# 3. The experiment is going on.
	time.sleep(args.duration + 5)

	# 4. Shut down.
	monitor.terminate()
	os.system('killall bwm-ng')
	os.system('killall iperf')

def run_experiment(pod,ip="127.0.0.1", port=6633, bw_h2c=10):
	"""
		Firstly, start up Mininet;
		secondly, generate traffics and test the performance of the network.
	"""
	# Create Topo.
	topo = NonBlocking(pod)
	topo.createNodes()
	topo.createLinks(bw_h2c=bw_h2c)

	# Start Mininet
	CONTROLLER_IP = ip
	CONTROLLER_PORT = port
	net = Mininet(topo=topo, link=TCLink, controller=None, autoSetMacs=True)
	net.addController(
		'controller', controller=RemoteController,
		ip=CONTROLLER_IP, port=CONTROLLER_PORT)
	net.start()

	# Set the OpenFlow version for switches as 1.3.0.
	topo.set_ovs_protocol_13()
	# Set the IP addresses for hosts.
	set_host_ip(net, topo)
	# Install proactive flow entries.
	install_proactive(net, topo)

	time.sleep(5)

	# 2. Generate traffics and test the performance of the network.
	traffic_generation(net, topo, iperf_peers.iperf_peers)

	# CLI(net)
	net.stop()

if __name__ == '__main__':
	setLogLevel('info')
	if os.getuid() != 0:
		logging.warning("You are NOT root!")
	elif os.getuid() == 0:
		run_experiment(args.k)   # run_experiment(4) or run_experiment(8)
