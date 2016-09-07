Introduction
============

Commissaire Service is a framework for writing long running services for the
Commissaire management system. It provides a standard way to connect to
Commissaire's bus and provide/consume services.

Example Use Cases
-----------------

Commissaire Investigator
````````````````````````
Commissaire's ``Investigator`` is a set of long running processes which
connect to and bootstrap new hosts wanting to be managed by Commissaire.


Commissaire Watcher
```````````````````
Commissaire's ``Watcher`` is a set of long running processes which
connect to hosts that have already been bootstrapped and checks their status.


Commissaire Storage
```````````````````
Commissaire's ``Storage`` is a set of long running processes which handle
persisting data to a data store.
