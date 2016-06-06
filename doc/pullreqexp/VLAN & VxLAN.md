
class: center, middle


# VLAN ID
# &
# VxLan Support 


Author: REN Xuancheng (jklj077@hotmail.com)

Source Code: https://github.com/jklj077/docklet/
---
## Issues & Goals
- **Issues**
    - Tenant is limited to 4094
        - as there are only 4096 vlan ids, 2 of which are reserved for special purpose
    - Virtual network infrastructure is fixed once initialized
        - vlan id pools
        - virtual switches & virtual tunnels


- **Goals**
    - Make it capable enough, 4094 is frustrating
    - Make it dynamic, do not set it up when not needed
---
## Design - Capability - Why VLAN
- **Broadcast Storm due to flooding**
    - L2: when switches learn the mapping of MAC addresses and ports
    - L3: when routers learn the mapping of interfaces and IP addresses


- **VLAN to the rescue**
    - Isolate L2 broadcast domain
    - Switches forward packages in terms of VLAN ID instead of MAC addresses
    - In associate with IP subnet management
        - A virtual LAN is an IP subnet


- **Docklet - using VLAN to deal with storm**
    - A user owns a VLAN ID
    - A user owns a IP subnet
    - Support 4096 users at most
---
## Design - Capability
- **Solution: Share**
    - A VLAN ID is assigned to more than one user
    - Advantages of VLAN are reduced for users using a shared VLAN ID
    - Divide users into groups, provide diversified service


- **Solution: Withdraw those that are not used** *implemented*
    - Users who have no workspace do not need a VLAN ID
    - The limitation still exists but is alleviated
        - If the users develop the habit of deleting unused workspace
        - If the users use workspace on a varied time bases


- **Solution: Subsititue VLAN**
    - VxLAN, millions of IDs(VNI)
        - A tunnel technique, based on UDP and IP muliticast
    - Bad News: difficult to use
        - openvswitch only supports VxLAN in a GRE way
            - configure tunnels by hand
        - linux kernal supports VxLan completely
            - configure tunnels by hand
            - auto configure tunnels using multicast
---
## A little more about VLAN & VxLAN
- **VLAN**
    - VLAN is used to separate links attached to a switch into groups
        - net -> subnet, "isolate"
    - VLAN ID (tag) is local
        - the valid domain ("namespace") is the net formed by connected, VLAN enabled switches
- **VxLAN**
    - VxLAN is used to connect separate nets to form a bigger net
        - subnet -> net, "merge"
    - VxLAN ID (VNI) is also "local"
        - the valid domain ("namespace") is the nets specified by an IP multicast address

- **VxLAN is not a substitution of VLAN**
    - it cannot serve as the role of VLAN as far as docklet scenario is concerned
        - that is, to isolate L2 broadcast domain
---
## Design - Capability
- **Solution: Extend Virtual Network Structure** *implemented*
    - Good News
        - VLAN ID is local
        - If switches are not connected via links, their VLAN configuration will be independent
            - we can make multiple "namespace"s

- **Final Design**
    - two level: namespace(switch), vlan
    - namespace: a namespace consists of several virtual switches, one on each host, connected by tunnels using key
    - vlan: a vlan is subject to a namespace and consists of containers belonging to a single user
    - This will allow (2^24 - 2) * (2^16 - 2) tenants at most 
---
## Design - Capability
- **Introducing netid**
    - Previously, a user managed by networkmgr is identified by its VLAN ID
    - It's not adequate now, as a user has a VLAN and a namespace the VLAN is subject to
    - For convenience, we introduce netid as a logical id
        - VLAN ID is computed as netid % USE_PER_SWITCH + 1
        - switch id (namespace) is computed as netid/USER_PER_SWITCH + 1
        - USER_PER_SWITCH mustn't exceed 4094
    - netid is assigned the way vlanid is assigned
        - manage using pools
        - allow withdraw
---
## Design - On Demand
- **The aforesaid design leads to new problems**
   - Too many netids, make all the id pools can be time-consuming, unnecessary and redundant
   - The virtual switches on each host have to be set up during worker initialization, including tunnels to the master
   - Most importantly, we need to pre-set the namespace count!!!
       - it's fixed, it's not scalable, it's bad

- **Make it dynamic**
---
## Design - On Demand
- **Solution: New Managers** *implemented*
    - netid manager
        - no pools when manager initializes
        - when need an id, get a valid pool or make a pool, pick one from the pool
        - when withdraw an id, get a valid pool, add the id to the pool
        - full pools are reseverd
    - virtual switch manager
        - manage virtual swtiches on workers from master
        - no virtual swtiches when a worker or a master initializes
        - when a user is managed by network manager
            - check the virtual switch on the master and setup a gateway
        - when a user adds a container
            - check the virtual switch on the worker and the tunnel between the virtual swtich on the master and the virtual switch on the worker
        - if a worker is lost, the tunnels on master are not deleted
    - issues: observable delay
---
## Design - On Demand
- **Solution: netid can reuse user id from user manager**
- **Solution: only record the max assigned netid**
    - no need to withdraw, there are just too many ids
    - issues: virtual switches with small ids will be redundant after some time 
- **Solution: set up virtual switch and tunnels in container up script**
    - nice, in terms of workers to the master
    - issues: fixed number of virtual switches (the master to workers)
---
## Experiments
- **Not much can be done, other than correctness check**
- **Correctness Check**
    - Not rigorous
    - Tested Configuration: one host hosts the master and a worker
    - Tested Configuration: two hosts, one hosts the master and a worker, the other hosts a worker
- **Performance**
    - Not Available
        - More than 4094 containers on one host?
---
## Summary
- **Task is network related**
- **Know more, Go deeper**
    - VLAN, VxLAN, GRE, open vswitch
- **A refinement of the current docklet virtual network structure is proposed**
    - two levels: swtich, vlan
    - introduce netid
    - introduce netid manager and virtual switches manager
- **Solutions have been considered, discussed, implemented and discarded**
    - Detour: VxLAN based one user per virtual switch, misunderstanding of VxLAN
    - Codes are almost all read
    - A workable sub system is coded
