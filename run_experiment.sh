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
	killall python
	killall -9 ryu-manager
	mn -c
	exit
}

trap ctrlc INT

# Output directory.
out_dir="./results"
rm -f -r ./results
mkdir -p $out_dir

# Run experiments.
for (( trial=1; trial<=flows_num_per_host; trial++ ))
do
	./run_experiment2.sh $k $cpu $trial $duration $out_dir

done


# # Plot results.
# sudo python ./plot_results.py --k $k --duration $duration --dir $out_dir
