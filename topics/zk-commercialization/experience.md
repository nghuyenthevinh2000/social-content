## This is my experience trying to push ZK technology in Viet Nam

Personal profile: ex - senior product owner at 1Matrix, working on Vietnam Blockchain Service Network, and lobbying for ZK technology to Government Cipher Committee

Some use cases were explored: database fragmentation was the biggest hurdle
1. ZK-DID for unified certificate verification in mother group: different companies in the same mother group in Viet Nam cannot share full information of a client to one another due to data law. Users would have to perform re-verification every time to different companies. Can verification data at one company be used for all others without revealing data? Initially, ZK seems like a good fit as it can prove without revealing. However even in the same mother group, different companies have different database structures requiring too much efforts to clean and unify them all. The cost is not justified just for saving user time.
2. ZK for public notary: a person has to reveal certificate information to get a notarized copies by the authority. If that person has a registry for all certificates, he can prove to companies without revealing personal information. But, this is only viable if there is a government entity with all the citizen certificate data first to enable a ZK layer on top. Eventually, we found out that databases in local government entities were so fragmented, that no one has all of it.

Other hurdles were found:
1. To government sector: ZK technology is a new proving scheme that requires national approval from Government Cipher Committee, without multiple rounds of effect study from the committee, the technology can't be used.

Questions to discuss to explore more Perspectives-Heuristics:
1. what are the most basic functions of ZK?
2. What other field problems can be easily solved with ZK basic functions? 