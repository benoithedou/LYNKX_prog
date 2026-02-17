# LYNKX Production Test Tool - Refactored

This is a refactored version of the production test tool with clean architecture.

## Architecture

```
tools/
├── core/           # Low-level transport and protocol
├── device/         # Device control and configuration
├── firmware/       # Firmware encryption and management
├── services/       # Business logic and workflows
├── ui/             # GUI components (Tkinter)
├── utils/          # Utilities (CRC, file operations)
└── main.py         # Application entry point
```

## Design Principles

- **Separation of Concerns**: UI, business logic, and hardware control are separated
- **No Global Variables**: All state is managed through class instances
- **Thread-Safe**: UART communication uses proper locking mechanisms
- **Event-Driven**: Components communicate via events/callbacks
- **Testable**: Each module can be tested independently

## Key Improvements

1. **UART Management**: Single `SerialManager` class manages all serial operations
2. **State Management**: `AppState` class holds application state
3. **Event System**: Components communicate via events instead of direct calls
4. **Dependency Injection**: Components receive dependencies in constructors
5. **Error Handling**: Proper exception propagation and user feedback
