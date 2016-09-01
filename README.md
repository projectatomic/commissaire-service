# commissaire-service
Prototype Commissaire Service Library


## Actions
## Service Action Invocations

Actions are an abstraction for remote invocation of methods.

```javascript
{
    'action': str, // Name of the remote method
    'args': dict   // Maps as keyword arguments to an on_action()
}
```

## Service Action Responses

```javascript
{
    'result': mixed,  // Can be int, str, dict, or list
    'exception': {    // Optional
        'type': str,
        'message': str,
    }
}
```

## Creating a Service

1. Subclass ``commissaire_service.service.CommissaireService``
1. Define all ``on_{{ action }}(self, message, ...)`` for specific calls
1. **Optional**: Define ``on_message(body, message))`` for non-action messages
