Major Project Synopsis

on

TRUSTRENT: A BLOCKCHAIN-BASED SECURITY DEPOSIT ESCROW AND VERIFIED TENANCY SYSTEM FOR THE INDIAN RENTAL MARKET

In partial fulfillment of requirements for the degree

of

BACHELOR OF TECHNOLOGY

IN

COMPUTER SCIENCE & ENGINEERING

Submitted by:

Aniket Parmar [23100BTCSAII14270]

Akhil Antony [23100BTCSAII14262]

Sameer Ajay Chauhan [23100BTCSAII14319]

Vansh Rana [22100BTCSAII11065]

Under the guidance of

PROF. Jagrati Nagdiya

DEPARTMENT OF COMPUTER SCIENCE & ENGINEERING

SHRI VAISHNAV INSTITUTE OF INFORMATION TECHNOLOGY

SHRI VAISHNAV VIDYAPEETH VISHWAVIDYALAYA, INDORE

JUL-DEC-2026

Abstract

Security deposits in the Indian rental market are usually held by the landlord alone, with no neutral custody, no tamper-proof record of the property's condition, and no affordable way to contest deductions. Tenants therefore face delayed or arbitrary refunds, while landlords lack reliable proof of genuine damage. This project proposes TrustRent, a blockchain-based security deposit escrow and verified tenancy system for the Indian rental market. The deposit is locked in a smart-contract vault on the Polygon test network that neither party controls alone. The vault follows an on-chain tenancy lifecycle from drafted to refunded, returns the deposit automatically to the tenant if the landlord raises no claim within an agreed window, and limits any deduction to a cap written into the lease. Hashes of the signed lease and of timestamped move-in and move-out evidence are anchored on-chain while the files are stored off-chain, and both parties are identity-verified before a vault opens. Disputed claims go to an arbitrator who reviews the on-chain evidence. Users interact through a web application built with a Node.js backend and a React frontend, with wallet-free, gasless onboarding delivered through social login and ERC-4337 account abstraction, and an indexer keeps the dashboards current. The prototype will take one tenancy from lease signing to refund, including a disputed case, and will be evaluated on gas cost, test coverage, and end-to-end behavior. A literature review shows that deposit custody, bounded deductions, and condition evidence are rarely addressed together in existing blockchain rental systems, and that no Indian rental platform offers neutral deposit custody together with a tamper-proof evidence trail. TrustRent aims to make deposit handling fair and auditable for both parties without requiring them to understand blockchain.

1. INTRODUCTION

A blockchain is a distributed ledger that records transactions in a tamper-evident chain of blocks, and smart contracts are programs on such a ledger that execute agreed terms automatically when conditions are met. Together they allow money to be held and released by rule without relying on a single trusted party. Large files are not stored on the chain; they are kept in systems such as the InterPlanetary File System (IPFS), and only their hashes are recorded [1].

In rental housing, the security deposit is a natural candidate for this approach. Chen et al. [1] built an Ethereum rental system in which the tenant pays the deposit into a lease contract, but the refund is settled by the landlord proposing an amount and the tenant accepting or rejecting it. Kibet et al. [2] proposed locking the deposit until the end of the tenancy with an arbitrator deciding disputes, but reported no implementation results. Tseng et al. [3] designed a government-supervised consortium architecture with verified identities that does not model deposit handling. Kleros [4] offers decentralized arbitration for smart contracts and names rental deposits as one use case.

In India, the Model Tenancy Act, 2021 recommends a two-month cap on residential deposits and digital tenancy records, but it is a model law that states adopt individually, and it does not provide neutral custody of the money [5]. Indian commercial platforms likewise digitise listings, agreements, and rent payments, or finance the deposit, but leave custody of the money with one party [7]–[10]. The reviewed academic work shows that deposit custody, bounded deductions, evidence of property condition, and affordable arbitration are rarely combined, and none of it targets India. This project addresses that combination.

2. PROBLEM DOMAIN

In the Indian residential rental market, the security deposit is held solely by the landlord. There is no neutral custody of the money, no tamper-proof record of the lease or the property's condition, and no affordable way to contest deductions. Tenants face arbitrary or delayed refunds, and landlords cannot reliably verify tenants or prove genuine damage. Existing platforms digitize listings, agreements, and rent payments but leave this trust gap around the deposit.

The problem breaks into five specific problems: one-sided deposit custody, no evidence baseline, mutable lease agreements, unverified parties, and unaffordable dispute resolution. Each is addressed by a module described in Section 3. The project asks whether a smart-contract escrow, combined with verified identities and an on-chain evidence trail, can make deposit handling fair and auditable for both sides without requiring either party to understand blockchain.

The objectives of the proposed work are:

1. Design and deploy a deposit vault smart contract with an automatic refund timeout, capped deductions, and arbitrator resolution.

2. Implement the tenancy state machine from drafted to refunded, emitting an event for every transition.

3. Anchor the lease and the move-in and move-out evidence as hashes on-chain, with files stored off-chain.

4. Verify landlord and tenant identity before a vault opens, without placing personal data on-chain.

5. Provide gasless, wallet-free onboarding through ERC-4337 account abstraction and social login.

6. Provide a web dashboard for tenants, landlords, and arbitrators, backed by an indexer for real-time status.

7. Evaluate the prototype on gas cost, test coverage, and an end-to-end tenancy including a dispute.

3. SOLUTION DOMAIN

TrustRent places the deposit in a vault contract that a factory contract creates for each tenancy. The tenancy moves through the states Drafted, Signed, Active, MoveOut, Disputed, and Refunded, and every transition emits an event. A tenancy becomes Signed only after both parties are verified and sign, and Active only after the deposit is locked and the move-in evidence is hashed. At the end of the lease, the move-out evidence is hashed. If the landlord raises no claim within an agreed number of days, the full deposit returns to the tenant automatically. A claim must reference the hashed evidence and cannot exceed the cap written into the lease, and a contested claim goes to an arbitrator who decides the split. Each of the five problems maps to a module: the vault with its auto-refund timeout addresses one-sided custody, timestamped evidence hashes address the missing evidence baseline, the anchored lease hash addresses mutable agreements, verified identity before a vault opens addresses unverified parties, and capped deductions with an arbitrator flow address unaffordable dispute resolution.

Registry contracts hold identity attestations and approved arbitrators, so only verified parties can open a vault. Personal data stays off-chain, and only hashes or attestations are recorded. The lease and evidence files are encrypted and stored off-chain, for example on IPFS, behind a storage interface so that providers can be swapped.

A Node.js backend provides authentication with social login, a mock identity verification service, file hashing and storage, and read endpoints, while a React frontend offers tenant, landlord, and arbitrator dashboards. An indexer built with The Graph reads the contract events and keeps dashboard status current. Wallet-free, gasless use is delivered through ERC-4337 account abstraction [6] and social login, so users never handle a wallet or pay gas fees.

The design applies object-oriented principles: a User base class with Tenant, Landlord, and Arbitrator subclasses, encapsulated attributes, and the Factory, State, Strategy, and Observer patterns. Development follows UML modeling, Jira sprints, Git feature branches with pull requests, and a GitHub Actions pipeline that runs tests on every pull request. The prototype uses a mock rupee token. A production version would hold rupees in regulated bank escrow, with the contract issuing release instructions.

4. SYSTEM DOMAIN

Software: Solidity 0.8.x with OpenZeppelin libraries for the contracts, Hardhat for compilation, testing, and deployment, and the Polygon Amoy test network; ERC-4337 account abstraction with social login for gasless, wallet-free use; Node.js with Express and PostgreSQL for the backend; The Graph for indexing contract events; React with ethers.js for the frontend; IPFS through a pinning service for off-chain files; Jest for backend tests; GitHub Actions for CI/CD; Jira and Git for project management; and Vercel and Render for hosting. Hardware: a development computer with at least 8 GB RAM, an internet connection, and free-tier cloud services.

Justification: Solidity and the Ethereum Virtual Machine form the most widely used smart-contract platform, and Polygon offers low-cost transactions for testing. Node.js is chosen because it lets the backend share JavaScript with the React frontend and with the ethers.js and Hardhat tooling used for the contracts. ERC-4337 account abstraction and social login remove the need for users to hold a wallet or pay gas, and The Graph indexes contract events so dashboards show real-time status without polling the chain. PostgreSQL stores off-chain data reliably. Hardhat and Jest support automated tests that the CI pipeline can run, and free hosting tiers keep the cost close to zero.

5. APPLICATION DOMAIN

TrustRent applies to residential rentals in Indian cities with large student and young-professional populations, such as Bengaluru, Mumbai, Pune, Hyderabad, and the National Capital Region. Tenants gain a refund that does not depend on goodwill, landlords gain proof for genuine claims, and arbitrators gain a clear evidence trail. Variants include paying guest and hostel stays, commercial leases with different deposit caps, and integration with listing platforms. Possible extensions are rent collection, regulated bank escrow through UPI, and machine-learning comparison of move-in and move-out photos. Listings, rent collection, real-money escrow, and mobile apps are out of scope for this phase.

6. EXPECTED OUTCOME

1. A working testnet prototype that takes one tenancy from signing to refund, including a disputed case.

2. Deployed and tested vault, factory, and registry contracts that emit events for every transition.

3. Web dashboards for tenant, landlord, and arbitrator, backed by an indexer for real-time status.

4. Gasless, wallet-free onboarding through ERC-4337 account abstraction and social login.

5. A measured evaluation of gas cost, test coverage, and end-to-end flow.

6. UML documentation, a CI/CD pipeline, and a live demo URL.

7. A review paper and an implementation paper.

7. REFERENCES

[1] Q.-L. Chen, R.-H. Ye, and F.-L. Lin, "A blockchain-based housing rental system," in Proc. Int. Conf. Adv. Comput. Technol., Inf. Sci. Commun. (CTISC), 2019, pp. 184–190, doi: 10.5220/0008097201840190.

[2] A. Kibet, M. M. Thiga, and S. M. Karume, "Towards a blockchain based smart contracts model design for housing market applications," Int. J. Adv. Res. Comput. Eng. Technol., vol. 8, no. 8, pp. 318–325, Aug. 2019.

[3] C.-H. Tseng, Y.-H. Hsieh, Y.-Y. Chang, and S.-M. Yuan, "Towards a trustworthy rental market: A blockchain-based housing system architecture," Electronics, vol. 14, no. 15, Art. no. 3121, Aug. 2025, doi: 10.3390/electronics14153121.

[4] C. Lesaege, F. Ast, and W. George, "Kleros short paper v1.0.7," Sep. 2019. [Online]. Available: https://kleros.io/assets/whitepaper.pdf

[5] Ministry of Housing and Urban Affairs, Government of India, "The Model Tenancy Act, 2021," New Delhi, India, 2021. [Online]. Available: https://prsindia.org/billtrack/the-model-tenancy-act-2021

[6] V. Buterin, Y. Weiss, K. Gazso, N. Patel, D. Tirosh, S. Nacson, and T. Hess, "ERC-4337: Account abstraction using alt mempool," Ethereum Improvement Proposals, Sep. 2021. [Online]. Available: https://eips.ethereum.org/EIPS/eip-4337

[7] NoBroker, "NoBroker rent agreement: Charges, online process, documents, and benefits." Accessed: Oct. 13, 2026. [Online]. Available: https://www.nobroker.in/rental-agreement/guides/nobroker-rent-agreement/

[8] "Housr launches zero-deposit renting solution powered by CirclePe," MediaBrief, Jul. 2026. Accessed: Oct. 13, 2026. [Online]. Available: https://mediabrief.com/housr-circlepe-launch-zero-deposit-renting-solution/

[9] "CirclePe," Dealroom.co company profile. Accessed: Oct. 13, 2026. [Online]. Available: https://app.dealroom.co/companies/circlepe

[10] "Cred's latest update brings a redesign and new finance products," TechRadar. Accessed: Oct. 13, 2026. [Online]. Available: https://www.techradar.com/news/creds-latest-update-brings-a-redesign-and-new-finance-products