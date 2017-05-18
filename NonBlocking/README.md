## NonBlocking

The so-called NonBlocking is the topology with only one switch connecting hosts, which is mainly used to test the bisection bandwidth and throughput in comparison experiments. Here, it is used to make comparison with fattree network, while "NonBlockingTopo4" means 16 (4^3/4 = 16) hosts and "NonBlockingTopo8" means 128 (8^3/4 = 128) hosts. The version of OpenFlow Protocol is 1.3.0.


### Download

Download files into Ryu directory, for instance, 'ryu/ryu/app/NonBlocking' is OK.


### Start

Firstly, start up the network. An example is shown below:

    $ sudo python ryu/ryu/app/NonBlocking/NonBlockingTopo4.py

And then, go into the top directory of Ryu, and run the application. An example is shown below:

    $ cd ryu
    $ ryu-manager --observe-links ryu/app/simple_switch_13.py

If the network has started up, test the correctness of it:

    mininet> pingall
    mininet> iperf


### Authors

Brought to you by Huang MaChi (Chongqing University of Posts and Telecommunications, Chongqing, China.) and Li Cheng (Beijing University of Posts and Telecommunications. www.muzixing.com).

If you have any question, email me. Don't forget to STAR this repository!

Enjoy it!
