#!/bin/bash
# Copyright (C) 2016 Huang MaChi at Chongqing University
# of Posts and Telecommunications, China.

k=$1
cpu=$2
flows_num_per_host=$3   # number of iperf flows per host.
duration=$4

# Exit on any failure.
set -e

# Check for uninitialized variables.
set -o nounset

ctrlc() {
	killall -9 python
	killall -9 ryu-manager
	mn -c
	exit
}

trap ctrlc INT

# Traffic patterns.
# "stag_0.2_0.3" means 20% under the same Edge switch,
# 30% between different Edge switches in the same Pod,
# and 50% between different Pods.
# "random" means choosing the iperf server randomly.
# Change it if needed.
traffics="stag1_0.2_0.3"

# Output directory.
out_dir="./results"
rm -f -r ./results
mkdir -p $out_dir

# Run experiments.
for traffic in $traffics
do
	# Create iperf peers.
	sudo python ./create_peers.py --k $k --traffic $traffic --fnum $flows_num_per_host
	sleep 1

	# NonBlocking
	dir=$out_dir/$flows_num_per_host/$traffic/NonBlocking
	mkdir -p $dir
	mn -c
	sudo python ./NonBlocking/NonBlocking.py --k $k --duration $duration --dir $dir --cpu $cpu




done
