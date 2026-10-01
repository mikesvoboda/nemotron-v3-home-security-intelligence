/**
 * @name FastAPI endpoint potentially missing authentication
 * @description Detects FastAPI POST/PUT/DELETE endpoints that may be missing
 *              authentication dependencies. Sensitive operations should require auth.
 * @kind problem
 * @problem.severity warning
 * @security-severity 6.0
 * @precision medium
 * @id py/fastapi-missing-auth
 * @tags security
 *       external/cwe/cwe-306
 */

import python

/**
 * A FastAPI route decorator call (`@app.post(...)`, `@router.delete(...)`, ...)
 * for a data-modifying HTTP method.
 *
 * The CodeQL Python library models the decorator expression of
 * `@app.post("/x")` as a `Call` whose function is an `Attribute` named after
 * the HTTP method; there is no `Decorator` class, and `Expr` has no
 * `getValue()`. The endpoint binding goes through `Function.getADecorator()`
 * (codeql/python-all, semmle/python/Function.qll) instead.
 */
class FastApiModifyingDecorator extends Call {
  FastApiModifyingDecorator() {
    this.getFunc().(Attribute).getName() in ["post", "put", "delete", "patch"]
  }

  string getMethod() { result = this.getFunc().(Attribute).getName() }

  /**
   * Gets the path argument from the decorator, if it is a string literal.
   */
  string getPath() {
    exists(StringLiteral sl | this.getArg(0) = sl | result = sl.getText())
  }
}

/**
 * A function decorated with a FastAPI route.
 */
class FastApiEndpoint extends Function {
  FastApiEndpoint() { this.getADecorator() instanceof FastApiModifyingDecorator }

  FastApiModifyingDecorator getRouteDecorator() { result = this.getADecorator() }

  /**
   * Checks if this endpoint has a dependency that looks like authentication.
   */
  predicate hasAuthDependency() {
    exists(Parameter p |
      p = this.getAnArg() and
      (
        // Look for Depends() with auth-related names
        exists(Call depends, Name depName |
          p.getDefault() = depends and
          depends.getFunc().(Name).getId() = "Depends" and
          depends.getArg(0) = depName and
          (
            depName.getId().toLowerCase().matches("%auth%") or
            depName.getId().toLowerCase().matches("%current_user%") or
            depName.getId().toLowerCase().matches("%verify%") or
            depName.getId().toLowerCase().matches("%require%") or
            depName.getId().toLowerCase().matches("%api_key%")
          )
        )
        or
        // Look for parameter names that suggest auth
        p.getName().toLowerCase().matches("%user%") or
        p.getName().toLowerCase().matches("%auth%") or
        p.getName().toLowerCase().matches("%token%")
      )
    )
  }

  /**
   * Checks if this is a health check or public endpoint that doesn't need auth.
   */
  predicate isExemptPath() {
    exists(string path | path = this.getRouteDecorator().getPath() |
      path.matches("%health%") or
      path.matches("%ready%") or
      path.matches("%live%") or
      path.matches("%ping%") or
      path.matches("%version%") or
      path.matches("%public%") or
      path.matches("%webhook%") // webhooks often have their own auth
    )
  }
}

from FastApiEndpoint endpoint
where
  not endpoint.hasAuthDependency() and
  not endpoint.isExemptPath() and
  // Focus on admin and sensitive-looking paths
  exists(string path | path = endpoint.getRouteDecorator().getPath() |
    path.matches("%admin%") or
    path.matches("%delete%") or
    path.matches("%config%") or
    path.matches("%setting%") or
    path.matches("%user%")
  )
select endpoint,
  "FastAPI " + endpoint.getRouteDecorator().getMethod().toUpperCase() +
    " endpoint may be missing authentication: " + endpoint.getRouteDecorator().getPath()
