## exp_BFlows

exp_BFlows is an experiment to compare the performance of BFlows with ECMP, PureSDN, Hedera and NonBlocking network.


### Prerequisites

The following softwares should have been installed in your machine.
* Mininet: git clone git://github.com/mininet/mininet; mininet/util/install.sh -a
* Ryu: git clone git://github.com/osrg/ryu.git; cd ryu; pip install .
* bwm-ng: apt-get install bwm-ng
* Networkx: pip install networkx
* Numpy: pip install numpy
* Matplotlib: apt-get install python-matplotlib


### Make some change

To register parsing parameters, you NEED to add the following code into the end of ryu/ryu/flags.py.

    CONF.register_cli_opts([
        # k_shortest_forwarding
        cfg.IntOpt('k_paths', default=4, help='number of candidate paths of KSP.'),
        cfg.StrOpt('weight', default='bw', help='weight type of computing shortest path.'),
        cfg.IntOpt('fanout', default=4, help='switch fanout number.')])


### Reinstall Ryu

You must reinstall Ryu, so that you can run the new code. In the top directory of Ryu project:

    sudo python setup.py install


### Start

Note: Before doing the experiment, you should change the controller's IP address from '192.168.56.101' to your own machine's eth0 IP address in the fattree.py module in each application, because '192.168.56.101' is my computer's eth0 IP address (Try 'ifconfig' in your Ubuntu to find out the eth0's IP address). Otherwise, the switches can't connect to the controller.

Just start it as follows, you will find the results in the 'results' directory.

    $ ./run_experiment.sh 4 2.0 1 60

or

    $ ./run_experiment.sh 8 5.0 3 60

The first parameter '4' means execute the experiment in a 'K=4' FatTree network; the second parameter '2.0' means the total CPUs allocated to the hosts; the third parameter '1' means each host launches one Iperf TCP flows, the last parameter '60' means the traffic will last for 60 seconds. It will takes you about 48 hours for the 'K=4' experiment.


### Author

Brought to you by Huang MaChi (Chongqing University of Posts and Telecommunications, Chongqing, China).

If you have any question, you can email me at huangmachi@foxmail.com.  Don't forget to STAR this repository!

Enjoy it!
