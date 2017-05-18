#!/bin/bash
# Copyright (C) 2016 Huang MaChi at Chongqing University
# of Posts and Telecommunications, China.

k=$1
cpu=$2
flowsPerHost=$3   # number of iperf flows per host.
duration=$4
out_dir=$5

# Exit on any failure.
set -e

# Check for uninitialized variables.
set -o nounset

ctrlc() {
	killall python
	killall -9 ryu-manager
	mn -c
	exit
}

trap ctrlc INT

# Traffic patterns.
# "stag_0.5_0.3" means 50% under the same Edge switch,
# 30% between different Edge switches in the same Pod,
# and 20% between different Pods.
# "random" means choosing the iperf server randomly.
# Change it if needed.
traffics="random1 random2 random3 random4 random5 random6 random7 random8 random9 random10 random11 random12 random13 random14 random15 random16 random17 random18 random19 random20 stag1_0.1_0.2 stag2_0.1_0.2 stag3_0.1_0.2 stag4_0.1_0.2 stag5_0.1_0.2 stag6_0.1_0.2 stag7_0.1_0.2 stag8_0.1_0.2 stag9_0.1_0.2 stag10_0.1_0.2 stag11_0.1_0.2 stag12_0.1_0.2 stag13_0.1_0.2 stag14_0.1_0.2 stag15_0.1_0.2 stag16_0.1_0.2 stag17_0.1_0.2 stag18_0.1_0.2 stag19_0.1_0.2 stag20_0.1_0.2 stag1_0.2_0.3 stag2_0.2_0.3 stag3_0.2_0.3 stag4_0.2_0.3 stag5_0.2_0.3 stag6_0.2_0.3 stag7_0.2_0.3 stag8_0.2_0.3 stag9_0.2_0.3 stag10_0.2_0.3 stag11_0.2_0.3 stag12_0.2_0.3 stag13_0.2_0.3 stag14_0.2_0.3 stag15_0.2_0.3 stag16_0.2_0.3 stag17_0.2_0.3 stag18_0.2_0.3 stag19_0.2_0.3 stag20_0.2_0.3 stag1_0.3_0.3 stag2_0.3_0.3 stag3_0.3_0.3 stag4_0.3_0.3 stag5_0.3_0.3 stag6_0.3_0.3 stag7_0.3_0.3 stag8_0.3_0.3 stag9_0.3_0.3 stag10_0.3_0.3 stag11_0.3_0.3 stag12_0.3_0.3 stag13_0.3_0.3 stag14_0.3_0.3 stag15_0.3_0.3 stag16_0.3_0.3 stag17_0.3_0.3 stag18_0.3_0.3 stag19_0.3_0.3 stag20_0.3_0.3 stag1_0.4_0.3 stag2_0.4_0.3 stag3_0.4_0.3 stag4_0.4_0.3 stag5_0.4_0.3 stag6_0.4_0.3 stag7_0.4_0.3 stag8_0.4_0.3 stag9_0.4_0.3 stag10_0.4_0.3 stag11_0.4_0.3 stag12_0.4_0.3 stag13_0.4_0.3 stag14_0.4_0.3 stag15_0.4_0.3 stag16_0.4_0.3 stag17_0.4_0.3 stag18_0.4_0.3 stag19_0.4_0.3 stag20_0.4_0.3 stag1_0.5_0.3 stag2_0.5_0.3 stag3_0.5_0.3 stag4_0.5_0.3 stag5_0.5_0.3 stag6_0.5_0.3 stag7_0.5_0.3 stag8_0.5_0.3 stag9_0.5_0.3 stag10_0.5_0.3 stag11_0.5_0.3 stag12_0.5_0.3 stag13_0.5_0.3 stag14_0.5_0.3 stag15_0.5_0.3 stag16_0.5_0.3 stag17_0.5_0.3 stag18_0.5_0.3 stag19_0.5_0.3 stag20_0.5_0.3 stag1_0.6_0.2 stag2_0.6_0.2 stag3_0.6_0.2 stag4_0.6_0.2 stag5_0.6_0.2 stag6_0.6_0.2 stag7_0.6_0.2 stag8_0.6_0.2 stag9_0.6_0.2 stag10_0.6_0.2 stag11_0.6_0.2 stag12_0.6_0.2 stag13_0.6_0.2 stag14_0.6_0.2 stag15_0.6_0.2 stag16_0.6_0.2 stag17_0.6_0.2 stag18_0.6_0.2 stag19_0.6_0.2 stag20_0.6_0.2 stag1_0.7_0.2 stag2_0.7_0.2 stag3_0.7_0.2 stag4_0.7_0.2 stag5_0.7_0.2 stag6_0.7_0.2 stag7_0.7_0.2 stag8_0.7_0.2 stag9_0.7_0.2 stag10_0.7_0.2 stag11_0.7_0.2 stag12_0.7_0.2 stag13_0.7_0.2 stag14_0.7_0.2 stag15_0.7_0.2 stag16_0.7_0.2 stag17_0.7_0.2 stag18_0.7_0.2 stag19_0.7_0.2 stag20_0.7_0.2 stag1_0.8_0.1 stag2_0.8_0.1 stag3_0.8_0.1 stag4_0.8_0.1 stag5_0.8_0.1 stag6_0.8_0.1 stag7_0.8_0.1 stag8_0.8_0.1 stag9_0.8_0.1 stag10_0.8_0.1 stag11_0.8_0.1 stag12_0.8_0.1 stag13_0.8_0.1 stag14_0.8_0.1 stag15_0.8_0.1 stag16_0.8_0.1 stag17_0.8_0.1 stag18_0.8_0.1 stag19_0.8_0.1 stag20_0.8_0.1"

# Run experiments.
for traffic in $traffics
do
	# Create iperf peers.
	sudo python ./create_peers.py --k $k --traffic $traffic --fnum $flowsPerHost
	sleep 1

	# BFlows
	dir=$out_dir/$flowsPerHost/$traffic/BFlows
	mkdir -p $dir
	mn -c
	sudo python ./BFlows/fattree.py --k $k --duration $duration --dir $dir --cpu $cpu

	# ECMP
	dir=$out_dir/$flowsPerHost/$traffic/ECMP
	mkdir -p $dir
	mn -c
	sudo python ./ECMP/fattree.py --k $k --duration $duration --dir $dir --cpu $cpu

	# PureSDN
	dir=$out_dir/$flowsPerHost/$traffic/PureSDN
	mkdir -p $dir
	mn -c
	sudo python ./PureSDN/fattree.py --k $k --duration $duration --dir $dir --cpu $cpu

	# Hedera
	dir=$out_dir/$flowsPerHost/$traffic/Hedera
	mkdir -p $dir
	mn -c
	sudo python ./Hedera/fattree.py --k $k --duration $duration --dir $dir --cpu $cpu

	# NonBlocking
	dir=$out_dir/$flowsPerHost/$traffic/NonBlocking
	mkdir -p $dir
	mn -c
	sudo python ./NonBlocking/NonBlocking.py --k $k --duration $duration --dir $dir --cpu $cpu

done


# Plot results.
# sudo python ./plot_results.py --k $k --duration $duration --dir $out_dir --fnum $flowsPerHost
