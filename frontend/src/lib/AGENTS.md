# Lib Directory - AI Agent Guide

## Purpose

This directory contains low-level functional programming utilities and type-safe error handling primitives. These are foundational building blocks used throughout the application for composing operations, managing errors without exceptions, and implementing timing controls.

## Key Files

| File              | Purpose                                                    | Lines |
| ----------------- | ---------------------------------------------------------- | ----- |
| `functional.ts`   | Function composition, currying, debounce, throttle, memoize | ~755  |
| `functional.test.ts` | Comprehensive tests for functional utilities            | ~740  |
| `result.ts`       | Rust-inspired Result type for type-safe error handling     | ~584  |
| `result.test.ts`  | Tests for Result type and utilities                        | ~616  |

## Key Exports

### functional.ts

#### Function Composition

| Export      | Signature                                | Description                              |
| ----------- | ---------------------------------------- | ---------------------------------------- |
| `pipe`      | `(...fns) => (arg) => result`            | Left-to-right function composition       |
| `compose`   | `(...fns) => (arg) => result`            | Right-to-left function composition       |

#### Currying

| Export      | Signature                                | Description                              |
| ----------- | ---------------------------------------- | ---------------------------------------- |
| `curry`     | `(fn: (a, b) => R) => curried`           | Curry a 2-argument function              |
| `curry3`    | `(fn: (a, b, c) => R) => curried`        | Curry a 3-argument function              |

#### Timing Control

| Export      | Signature                                | Description                              |
| ----------- | ---------------------------------------- | ---------------------------------------- |
| `debounce`  | `(fn, wait, options?) => DebouncedFn`    | Delay until wait ms after last call      |
| `throttle`  | `(fn, wait, options?) => ThrottledFn`    | At most once per wait ms                 |

#### Additional Utilities

| Export      | Signature                                | Description                              |
| ----------- | ---------------------------------------- | ---------------------------------------- |
| `once`      | `(fn) => fn`                             | Call at most once, cache result          |
| `memoize`   | `(fn, getKey?) => fn`                    | Cache results by argument                |
| `negate`    | `(predicate) => predicate`               | Logical NOT of predicate                 |
| `constant`  | `(value) => () => value`                 | Always returns same value                |
| `identity`  | `(value) => value`                       | Returns argument unchanged               |

### result.ts

#### Core Types

| Export      | Description                                                  |
| ----------- | ------------------------------------------------------------ |
| `Result<T, E>` | Discriminated union: `Ok<T> | Err<E>`                     |
| `Ok<T>`     | Success result containing a value                            |
| `Err<E>`    | Error result containing an error                             |

#### Factory Functions

| Export      | Signature                    | Description                              |
| ----------- | ---------------------------- | ---------------------------------------- |
| `ok`        | `(value: T) => Ok<T>`        | Create success result                    |
| `err`       | `(error: E) => Err<E>`       | Create error result                      |

#### Type Guards

| Export      | Signature                                | Description                              |
| ----------- | ---------------------------------------- | ---------------------------------------- |
| `isOk`      | `(result) => result is Ok<T>`            | Check if result is success               |
| `isErr`     | `(result) => result is Err<E>`           | Check if result is error                 |

#### Transformations

| Export      | Signature                                | Description                              |
| ----------- | ---------------------------------------- | ---------------------------------------- |
| `map`       | `(result, fn) => Result<U, E>`           | Transform success value                  |
| `mapErr`    | `(result, fn) => Result<T, F>`           | Transform error value                    |
| `flatMap`   | `(result, fn) => Result<U, E>`           | Chain result-returning functions         |
| `andThen`   | Alias for `flatMap`                      | Alternative name for flatMap             |

#### Extraction

| Export         | Signature                             | Description                              |
| -------------- | ------------------------------------- | ---------------------------------------- |
| `unwrap`       | `(result) => T`                       | Get value or throw error                 |
| `unwrapOr`     | `(result, default) => T`              | Get value or return default              |
| `unwrapOrElse` | `(result, fn) => T`                   | Get value or compute from error          |
| `unwrapErr`    | `(result) => E`                       | Get error or throw                       |
| `match`        | `(result, {onOk, onErr}) => U`        | Pattern match on result                  |

#### Async Utilities

| Export         | Signature                             | Description                              |
| -------------- | ------------------------------------- | ---------------------------------------- |
| `fromPromise`  | `(promise) => Promise<Result<T, E>>`  | Convert Promise to Result                |
| `toPromise`    | `(result) => Promise<T>`              | Convert Result to Promise                |

#### Combining Results

| Export      | Signature                                | Description                              |
| ----------- | ---------------------------------------- | ---------------------------------------- |
| `all`       | `(results) => Result<T[], E>`            | Combine array of results                 |
| `allTuple`  | `(results) => Result<Tuple, E>`          | Combine tuple preserving types           |

## Usage Patterns

### Function Composition

```typescript
import { pipe, curry } from '@/lib/functional';

// Data transformation pipeline
const processUser = pipe(
  (user: User) => user.name,
  (name: string) => name.trim(),
  (name: string) => name.toUpperCase()
);

// Curried functions for partial application
const add = curry((a: number, b: number) => a + b);
const add5 = add(5);
[1, 2, 3].map(add5); // [6, 7, 8]
```

### Debounce/Throttle

```typescript
import { debounce, throttle } from '@/lib/functional';

// Search input - wait 300ms after user stops typing
const debouncedSearch = debounce((query: string) => {
  fetchResults(query);
}, 300);

// Scroll handler - at most once per 100ms
const throttledScroll = throttle(() => {
  updateScrollPosition();
}, 100);
```

### Result Type for Error Handling

```typescript
import { ok, err, isOk, map, flatMap, unwrapOr } from '@/lib/result';

// Return Result instead of throwing
function parseJSON<T>(json: string): Result<T, Error> {
  try {
    return ok(JSON.parse(json) as T);
  } catch (e) {
    return err(e as Error);
  }
}

// Chain validations
function validateUser(input: unknown): Result<User, string> {
  return flatMap(
    flatMap(parseJSON(input), validateName),
    validateEmail
  );
}

// Handle result with default
const user = unwrapOr(validateUser(input), defaultUser);

// Pattern matching
const message = match(result, {
  onOk: (value) => `Success: ${value}`,
  onErr: (error) => `Error: ${error}`,
});
```

### Async Operations

```typescript
import { fromPromise, toPromise, all } from '@/lib/result';

// Wrap async operations
const result = await fromPromise(fetch('/api/data'));

if (isOk(result)) {
  const response = result.value;
}

// Combine multiple async results
const results = await Promise.all([
  fromPromise(fetchUser(1)),
  fromPromise(fetchUser(2)),
]);
const combined = all(results);
```

## Design Principles

1. **No External Dependencies**: Pure TypeScript implementations without lodash or fp-ts
2. **Type Safety First**: Full TypeScript generics for compile-time type checking
3. **Immutable by Default**: Functions return new values, never mutate inputs
4. **Explicit Error Handling**: Result type makes error cases visible in types
5. **Composable**: Small functions that combine into larger behaviors

## Testing

Tests are co-located and cover:

- All function overloads for composition
- Edge cases (empty inputs, single functions)
- Timing behavior with fake timers
- Type narrowing with type guards
- Async/Promise interop

```bash
# Run lib tests
cd frontend && npm test src/lib/
```

## Notes for AI Agents

- **Use Result over try/catch**: Prefer returning `Result<T, E>` for fallible operations
- **Prefer pipe over compose**: `pipe` reads left-to-right matching data flow
- **Debounce for search**: Use `debounce` for search inputs, form validation
- **Throttle for scroll**: Use `throttle` for scroll, resize, mouse move handlers
- **Memoize expensive calls**: Use `memoize` for computationally expensive functions
- **Type guards narrow types**: `isOk(result)` narrows to `Ok<T>` in if blocks
- **flatMap for chaining**: Use `flatMap` to chain operations that return Results
