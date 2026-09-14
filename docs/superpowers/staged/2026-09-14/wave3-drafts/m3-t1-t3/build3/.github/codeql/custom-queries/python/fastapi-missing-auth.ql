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
 * A FastAPI route decorator (post, put, delete, patch) that modifies data.
 */
class FastApiModifyingDecorator extends Decorator {
  string method;

  FastApiModifyingDecorator() {
    exists(Call call, Attribute attr |
      this.getValue() = call and
      call.getFunc() = attr and
      (
        attr.getName() = "post" or
        attr.getName() = "put" or
        attr.getName() = "delete" or
        attr.getName() = "patch"
      ) and
      method = attr.getName()
    )
  }

  string getMethod() { result = method }

  /**
   * Gets the path argument from the decorator.
   */
  string getPath() {
    exists(Call call, StringLiteral sl |
      this.getValue() = call and
      call.getArg(0) = sl and
      result = sl.getText()
    )
  }
}

/**
 * A function decorated with a FastAPI route.
 */
class FastApiEndpoint extends Function {
  FastApiModifyingDecorator decorator;

  FastApiEndpoint() { this.getADecorator() = decorator }

  FastApiModifyingDecorator getRouteDecorator() { result = decorator }

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
    exists(string path | path = decorator.getPath() |
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
