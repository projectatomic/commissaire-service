Writing a Service
=================

High Level
----------

* Subclass ``commissaire_service.service.CommissaireService``
* Define all ``on_{{ action }}`` methods to exposed them on the bus
* **Optional**: Define ``on_message`` for handling unhandled messages

Code Example
------------

.. literalinclude:: ../../example/simpleservice.py
