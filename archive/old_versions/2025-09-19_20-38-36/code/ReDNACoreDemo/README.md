# ReDNACoreDemo

**ReDNACoreDemo** is a prototype implementation of the ReDNA **Core**.  
It acts as the **source of truth** for a User’s ReDNA (digital twin), handling:

- Storage of DNA hierarchies and evidence  
- Auditing and provenance tracking  
- Event logging and security enforcement  
- A hard connector API for integration with engines (UCN/RR) and explorers  

Other systems (e.g., coaches, explorers, or external apps) should connect through the **hard connector** rather than accessing internal state directly.

---

## Project Structure