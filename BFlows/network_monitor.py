# Copyright (C) 2016 Huang MaChi at Chongqing University
# of Posts and Telecommunications, Chongqing, China.
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

from __future__ import division
import copy
from operator import attrgetter

from ryu import cfg
from ryu.base import app_manager
from ryu.base.app_manager import lookup_service_brick
from ryu.controller import ofp_event
from ryu.controller.handler import MAIN_DISPATCHER, DEAD_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.lib import hub

import setting


CONF = cfg.CONF


class NetworkMonitor(app_manager.RyuApp):
	"""
		NetworkMonitor is a Ryu app for collecting traffic information.
	"""
	OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

	def __init__(self, *args, **kwargs):
		super(NetworkMonitor, self).__init__(*args, **kwargs)
		self.name = 'monitor'
		self.datapaths = {}
		self.port_stats = {}
		self.port_speed = {}
		self.stats = {}
		self.port_features = {}
		self.flow_num = {}   # self.flow_num = {dpid:{port_no:fnum,},}
		self.free_bandwidth = {}   # self.free_bandwidth = {dpid:{port_no:free_bw,},} unit:Kbit/s
		self.awareness = lookup_service_brick('awareness')
		self.graph = None
		self.best_paths = None

		# Start to green thread to monitor traffic and calculating
		# flow number of links respectively.
		self.monitor_thread = hub.spawn(self._monitor)
		self.save_fnum_thread = hub.spawn(self._save_fnum_graph)

	def _monitor(self):
		"""
			Main entry method of monitoring traffic.
		"""
		while CONF.weight == 'fnum':
			self.stats['port'] = {}
			for dp in self.datapaths.values():
				self.port_features.setdefault(dp.id, {})
				self._request_stats(dp)
			# Refresh data.
			self.best_paths = None
			hub.sleep(setting.MONITOR_PERIOD)
			if self.stats['port']:
				self.show_stat()
				hub.sleep(1)

	def _save_fnum_graph(self):
		"""
			Save flow number data into networkx graph object.
		"""
		while CONF.weight == 'fnum':
			self.graph = self.create_fnum_graph(self.flow_num)
			self.logger.debug("save flow number")
			self.create_bw_graph(self.graph, self.free_bandwidth)
			self.logger.debug("save free bandwidth")
			hub.sleep(setting.MONITOR_PERIOD)

	@set_ev_cls(ofp_event.EventOFPStateChange,
				[MAIN_DISPATCHER, DEAD_DISPATCHER])
	def _state_change_handler(self, ev):
		"""
			Record datapath information.
		"""
		datapath = ev.datapath
		if ev.state == MAIN_DISPATCHER:
			if not datapath.id in self.datapaths:
				self.logger.debug('register datapath: %016x', datapath.id)
				self.datapaths[datapath.id] = datapath
		elif ev.state == DEAD_DISPATCHER:
			if datapath.id in self.datapaths:
				self.logger.debug('unregister datapath: %016x', datapath.id)
				del self.datapaths[datapath.id]
		else:
			pass

	@set_ev_cls(ofp_event.EventOFPFlowStatsReply, MAIN_DISPATCHER)
	def _flow_stats_reply_handler(self, ev):
		"""
			Calculate flow speed and Save it.
			Note: table-miss, LLDP and ARP flow entries are not what we need, just filter them.
		"""
		body = ev.msg.body
		dpid = ev.msg.datapath.id
		self.flow_num.setdefault(dpid, {})
		for stat in sorted([flow for flow in body if (flow.priority not in [0, 65535])]):
			# Get flow's speed and record it.
			duration = self._get_time(stat.duration_sec, stat.duration_nsec)
			if duration < 0.1:
				duration = 0.1
			speed = float(stat.byte_count) / duration   # unit: byte/s
			_speed = speed * 8.0 / (setting.MAX_CAPACITY * 1000)
			if _speed >= 0.05:
				self._save_fnum(dpid, stat.instructions[0].actions[0].port)

	@set_ev_cls(ofp_event.EventOFPPortStatsReply, MAIN_DISPATCHER)
	def _port_stats_reply_handler(self, ev):
		"""
			Save port's stats information into self.port_stats.
			Calculate port speed and Save it.
			self.port_stats = {(dpid, port_no):[(tx_bytes, rx_bytes, rx_errors, duration_sec,  duration_nsec),],}
			self.port_speed = {(dpid, port_no):[speed,],}
			Note: The transmit performance and receive performance are independent of a port.
			We calculate the load of a port only using tx_bytes.
		"""
		body = ev.msg.body
		dpid = ev.msg.datapath.id
		self.stats['port'][dpid] = body
		self.free_bandwidth.setdefault(dpid, {})

		for stat in sorted(body, key=attrgetter('port_no')):
			port_no = stat.port_no
			if port_no != ofproto_v1_3.OFPP_LOCAL:
				key = (dpid, port_no)
				value = (stat.tx_bytes, stat.rx_bytes, stat.rx_errors,
						 stat.duration_sec, stat.duration_nsec)
				self._save_stats(self.port_stats, key, value, 5)

				# Get port speed and Save it.
				pre = 0
				period = setting.MONITOR_PERIOD
				tmp = self.port_stats[key]
				if len(tmp) > 1:
					# Calculate only the tx_bytes, not the rx_bytes. (hmc)
					pre = tmp[-2][0]
					period = self._get_period(tmp[-1][3], tmp[-1][4], tmp[-2][3], tmp[-2][4])
				speed = self._get_speed(self.port_stats[key][-1][0], pre, period)
				self._save_stats(self.port_speed, key, speed, 5)
				self._save_freebandwidth(dpid, port_no, speed)

	@set_ev_cls(ofp_event.EventOFPPortDescStatsReply, MAIN_DISPATCHER)
	def port_desc_stats_reply_handler(self, ev):
		"""
			Save port description info.
		"""
		msg = ev.msg
		dpid = msg.datapath.id
		ofproto = msg.datapath.ofproto

		config_dict = {ofproto.OFPPC_PORT_DOWN: "Down",
					   ofproto.OFPPC_NO_RECV: "No Recv",
					   ofproto.OFPPC_NO_FWD: "No Farward",
					   ofproto.OFPPC_NO_PACKET_IN: "No Packet-in"}

		state_dict = {ofproto.OFPPS_LINK_DOWN: "Down",
					  ofproto.OFPPS_BLOCKED: "Blocked",
					  ofproto.OFPPS_LIVE: "Live"}

		ports = []
		for p in ev.msg.body:
			ports.append('port_no=%d hw_addr=%s name=%s config=0x%08x '
						 'state=0x%08x curr=0x%08x advertised=0x%08x '
						 'supported=0x%08x peer=0x%08x curr_speed=%d '
						 'max_speed=%d' %
						 (p.port_no, p.hw_addr,
						  p.name, p.config,
						  p.state, p.curr, p.advertised,
						  p.supported, p.peer, p.curr_speed,
						  p.max_speed))

			if p.config in config_dict:
				config = config_dict[p.config]
			else:
				config = "up"

			if p.state in state_dict:
				state = state_dict[p.state]
			else:
				state = "up"

			# Recording data.
			port_feature = (config, state, p.curr_speed)
			self.port_features[dpid][p.port_no] = port_feature

	@set_ev_cls(ofp_event.EventOFPPortStatus, MAIN_DISPATCHER)
	def _port_status_handler(self, ev):
		"""
			Handle the port status changed event.
		"""
		msg = ev.msg
		ofproto = msg.datapath.ofproto
		reason = msg.reason
		dpid = msg.datapath.id
		port_no = msg.desc.port_no

		reason_dict = {ofproto.OFPPR_ADD: "added",
					   ofproto.OFPPR_DELETE: "deleted",
					   ofproto.OFPPR_MODIFY: "modified", }

		if reason in reason_dict:
			print "switch%d: port %s %s" % (dpid, reason_dict[reason], port_no)
		else:
			print "switch%d: Illeagal port state %s %s" % (dpid, port_no, reason)

	def _request_stats(self, datapath):
		"""
			Sending request msg to datapath
		"""
		self.logger.debug('send stats request: %016x', datapath.id)
		ofproto = datapath.ofproto
		parser = datapath.ofproto_parser
		req = parser.OFPPortDescStatsRequest(datapath, 0)
		datapath.send_msg(req)
		req = parser.OFPPortStatsRequest(datapath, 0, ofproto.OFPP_ANY)
		datapath.send_msg(req)
		req = parser.OFPFlowStatsRequest(datapath)
		datapath.send_msg(req)

	def get_max_fnum_of_links(self, graph, path, max_fnum):
		"""
			Get flow number of path.
		"""
		_len = len(path)
		if _len > 1:
			max_flownum = max_fnum
			for i in xrange(_len-1):
				pre, curr = path[i], path[i+1]
				if 'fnum' in graph[pre][curr]:
					_fnum = graph[pre][curr]['fnum']
					max_flownum = max(_fnum, max_flownum)
				else:
					continue
			return max_flownum
		else:
			return max_fnum

	def get_min_bw_of_links(self, graph, path, min_bw):
		"""
			Getting bandwidth of path. Actually, the mininum bandwidth
			of links is the path's bandwith, because it is the bottleneck of path.
		"""
		_len = len(path)
		if _len > 1:
			minimal_band_width = min_bw
			for i in xrange(_len-1):
				pre, curr = path[i], path[i+1]
				if 'bandwidth' in graph[pre][curr]:
					bw = graph[pre][curr]['bandwidth']
					minimal_band_width = min(bw, minimal_band_width)
				else:
					continue
			return minimal_band_width
		else:
			return min_bw

	def get_best_path_by_fnum(self, graph, paths):
		"""
			Get best path by comparing paths.
			Note: This function is called in BFlows module.
		"""
		best_paths = copy.deepcopy(paths)
		fnum_of_paths = copy.deepcopy(paths)

		# Reset the fnum_of_paths data structure.
		for src in fnum_of_paths.keys():
			for dst in fnum_of_paths[src].keys():
				fnum_of_paths[src][dst] = {}

		# Calculate the flow number of each path and save it.
		for src in paths:
			for dst in paths[src]:
				if src == dst:
					best_paths[src][src] = [src]
				else:
					for path in paths[src][dst]:
						max_fnum = 0
						max_fnum = self.get_max_fnum_of_links(graph, path, max_fnum)
						fnum_of_paths[src][dst].setdefault(max_fnum, [])
						fnum_of_paths[src][dst][max_fnum].append(path)

					# Get the least flow number paths and find the lightest-load one of them.
					min_fnum = min(fnum_of_paths[src][dst].keys())
					max_bw_of_paths = 0
					best_path = fnum_of_paths[src][dst][min_fnum][0]
					for path in fnum_of_paths[src][dst][min_fnum]:
						min_bw = setting.MAX_CAPACITY
						min_bw = self.get_min_bw_of_links(graph, path, min_bw)
						if min_bw > max_bw_of_paths:
							max_bw_of_paths = min_bw
							best_path = path
					best_paths[src][dst] = best_path

		self.best_paths = best_paths
		return best_paths

	def zero_dictionary(self, fnum_dict):
		for sw in fnum_dict.keys():
			for port in fnum_dict[sw].keys():
				fnum_dict[sw][port] = 0

	def create_fnum_graph(self, fnum_dict):
		"""
			Save flow number data into networkx graph object.
			self.flow_num = {dpid:{port_no:fnum,},}
		"""
		try:
			graph = self.awareness.graph
			link_to_port = self.awareness.link_to_port
			for link, port in link_to_port.items():
				(src_dpid, dst_dpid) = link
				(src_port, dst_port) = port
				if fnum_dict.has_key(src_dpid) and fnum_dict[src_dpid].has_key(src_port):
					fnum = fnum_dict[src_dpid][src_port]
					# Add key-value pair of flow number into graph.
					if graph.has_edge(src_dpid, dst_dpid):
						graph[src_dpid][dst_dpid]['fnum'] = fnum
					else:
						graph.add_edge(src_dpid, dst_dpid)
						graph[src_dpid][dst_dpid]['fnum'] = fnum
				else:
					if graph.has_edge(src_dpid, dst_dpid):
						graph[src_dpid][dst_dpid]['fnum'] = 0
					else:
						graph.add_edge(src_dpid, dst_dpid)
						graph[src_dpid][dst_dpid]['fnum'] = 0
			# print 'fnum_dict:', fnum_dict
			# Zero the flow_num dictionary.
			self.zero_dictionary(fnum_dict)
			return graph
		except:
			self.logger.info("Create flow number graph exception")
			if self.awareness is None:
				self.awareness = lookup_service_brick('awareness')
			# print 'fnum_dict:', fnum_dict
			# Zero the flow_num dictionary.
			self.zero_dictionary(fnum_dict)
			return self.awareness.graph

	def _save_fnum(self, dpid, port_no):
		"""
			Record flow number of port.
			port_feature = (config, state, p.curr_speed)
			self.port_features[dpid][p.port_no] = port_feature
			self.flow_num = {dpid:{port_no:num,},}
		"""
		port_state = self.port_features.get(dpid).get(port_no)
		if port_state:
			self.flow_num[dpid].setdefault(port_no, 0)
			self.flow_num[dpid][port_no] += 1
		else:
			self.logger.info("Port is Down")

	def create_bw_graph(self, graph, bw_dict):
		"""
			Save bandwidth data into networkx graph object.
		"""
		try:
			link_to_port = self.awareness.link_to_port
			for link, port in link_to_port.items():
				(src_dpid, dst_dpid) = link
				(src_port, dst_port) = port
				if src_dpid in bw_dict and dst_dpid in bw_dict:
					bandwidth = bw_dict[src_dpid][src_port]
					# Add key-value pair of bandwidth into graph.
					if graph.has_edge(src_dpid, dst_dpid):
						graph[src_dpid][dst_dpid]['bandwidth'] = bandwidth
					else:
						graph.add_edge(src_dpid, dst_dpid)
						graph[src_dpid][dst_dpid]['bandwidth'] = bandwidth
				else:
					if graph.has_edge(src_dpid, dst_dpid):
						graph[src_dpid][dst_dpid]['bandwidth'] = 0
					else:
						graph.add_edge(src_dpid, dst_dpid)
						graph[src_dpid][dst_dpid]['bandwidth'] = 0
		except:
			self.logger.info("Create bw graph exception")
			if self.awareness is None:
				self.awareness = lookup_service_brick('awareness')

	def _save_freebandwidth(self, dpid, port_no, speed):
		"""
			Calculate free bandwidth of port and Save it.
			port_feature = (config, state, p.curr_speed)
			self.port_features[dpid][p.port_no] = port_feature
			self.free_bandwidth = {dpid:{port_no:free_bw,},}
		"""
		port_state = self.port_features.get(dpid).get(port_no)
		if port_state:
			capacity = 10000   # The true bandwidth of link, instead of 'curr_speed'.
			free_bw = self._get_free_bw(capacity, speed)
			self.free_bandwidth[dpid].setdefault(port_no, None)
			self.free_bandwidth[dpid][port_no] = free_bw
		else:
			self.logger.info("Port is Down")

	def _save_stats(self, _dict, key, value, length=5):
		if key not in _dict:
			_dict[key] = []
		_dict[key].append(value)
		if len(_dict[key]) > length:
			_dict[key].pop(0)

	def _get_free_bw(self, capacity, speed):
		# freebw: Kbit/s
		return max(capacity - speed * 8 / 1000.0, 0)

	def _get_speed(self, now, pre, period):
		if period:
			return (now - pre) / (period)
		else:
			return 0

	def _get_time(self, sec, nsec):
		return sec + nsec / 1000000000.0

	def _get_period(self, n_sec, n_nsec, p_sec, p_nsec):
		return self._get_time(n_sec, n_nsec) - self._get_time(p_sec, p_nsec)

	def show_stat(self):
		'''
			Show statistics information.
		'''
		if setting.TOSHOW is False:
			return

		bodys = self.stats['port']
		print('\ndatapath  port '
			'   rx-pkts     rx-bytes ''   tx-pkts     tx-bytes '
			' port-bw(Kb/s)  port-speed(b/s)  port-freebw(Kb/s) '
			' port-state  link-state')
		print('--------  ----  '
			'---------  -----------  ''---------  -----------  '
			'-------------  ---------------  -----------------  '
			'----------  ----------')
		_format = '%8d  %4x  %9d  %11d  %9d  %11d  %13d  %15.1f  %17.1f  %10s  %10s'
		for dpid in sorted(bodys.keys()):
			for stat in sorted(bodys[dpid], key=attrgetter('port_no')):
				if stat.port_no != ofproto_v1_3.OFPP_LOCAL:
					print(_format % (
						dpid, stat.port_no,
						stat.rx_packets, stat.rx_bytes,
						stat.tx_packets, stat.tx_bytes,
						setting.MAX_CAPACITY,
						abs(self.port_speed[(dpid, stat.port_no)][-1] * 8),
						self.free_bandwidth[dpid][stat.port_no],
						self.port_features[dpid][stat.port_no][0],
						self.port_features[dpid][stat.port_no][1]))
		print
