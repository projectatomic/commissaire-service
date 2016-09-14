# commissaire-service
Commissaire Service Framework

[![Documentation](https://readthedocs.org/projects/commissaire/badge/?version=latest)](http://commissaire.readthedocs.org/) [![Build Status](https://travis-ci.org/projectatomic/commissaire-service.svg)](https://travis-ci.org/projectatomic/commissaire-service)

## Invocations
The library uses [jsonrpc v2](http://www.jsonrpc.org/specification) for remote
invocation and notifications internals.

**Note**: The last element for the ``routing_key`` must match the method to be called

## Example

```javascript
{
    "jsonrpc": "2.0",                             // Required header noting version of jsonrpc
    "id": "6829688e-649d-4de7-8649-afefca88781d", // Unique message id
    "method": "add",                              // The remote method to call
    "params": [1, 2]                              // The remote parameters to provide to the method
}
```

## Example Response
```javascript
{
    "jsonrpc": "2.0",                             // Required header noting version of jsonrpc
    "id": "6829688e-649d-4de7-8649-afefca88781d", // Unique message id
    "result": 3                                   // Result of the call
}
```

## Example Error
```javascript
{
    "jsonrpc": "2.0",                             // Required header noting version of jsonrpc
    "id": "6829688e-649d-4de7-8649-afefca88781d", // Unique message id
    "error": {
        "code": -32602,                           // http://www.jsonrpc.org/specification#error_object
        "message": "Method not found"             // Error message or Exception message
        "data": {                                 // Houses exception
            "exception": "TypeError"              // The name of the exception class or None
        }
    }
}
```

## Creating a Service

See the [documentation](http://commissaire.readthedocs.org/).
