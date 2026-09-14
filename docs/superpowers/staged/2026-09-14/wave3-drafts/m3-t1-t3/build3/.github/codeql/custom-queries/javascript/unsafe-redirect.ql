/**
 * @name Unvalidated redirect URL
 * @description Detects navigation to URLs that may be controlled by user input,
 *              which could lead to open redirect vulnerabilities.
 * @kind problem
 * @problem.severity warning
 * @security-severity 6.0
 * @precision medium
 * @id js/unsafe-redirect
 * @tags security
 *       external/cwe/cwe-601
 */

import javascript

/**
 * A call that navigates to a URL.
 */
class NavigationCall extends Expr {
  string navigationType;

  NavigationCall() {
    // window.location assignments
    exists(AssignExpr ae, PropAccess pa |
      this = ae and
      ae.getLhs() = pa and
      pa.getPropertyName() = "href" and
      navigationType = "location.href"
    )
    or
    // window.location.replace()
    exists(MethodCallExpr mc, PropAccess pa |
      this = mc and
      mc.getReceiver() = pa and
      (
        pa.getPropertyName() = "location" and
        mc.getMethodName() = "replace" and
        navigationType = "location.replace"
        or
        pa.getPropertyName() = "location" and
        mc.getMethodName() = "assign" and
        navigationType = "location.assign"
      )
    )
    or
    // window.open()
    exists(CallExpr ce |
      this = ce and
      ce.getCalleeName() = "open" and
      navigationType = "window.open"
    )
    or
    // React Router navigate
    exists(CallExpr ce |
      this = ce and
      ce.getCalleeName() = "navigate" and
      navigationType = "navigate"
    )
  }

  string getNavigationType() { result = navigationType }
}

/**
 * A URL parameter or query string access.
 */
class UrlParamAccess extends Expr {
  UrlParamAccess() {
    // URLSearchParams.get()
    exists(MethodCallExpr mc |
      this = mc and
      mc.getMethodName() = "get" and
      mc.getReceiver().getType().toString().matches("%URLSearchParams%")
    )
    or
    // useSearchParams hook
    exists(PropAccess pa |
      this = pa and
      pa.getBase().(CallExpr).getCalleeName() = "useSearchParams"
    )
    or
    // Direct URL query access
    exists(PropAccess pa |
      this = pa and
      pa.getPropertyName() = "search"
    )
  }
}

from NavigationCall nav, DataFlow::Node source, DataFlow::Node sink
where
  // This is a simplified check - a full analysis would use taint tracking
  source.asExpr() instanceof UrlParamAccess and
  sink.asExpr() = nav and
  // Check if they're in the same function
  source.asExpr().getEnclosingFunction() = nav.getEnclosingFunction()
select nav,
  "Navigation using " + nav.getNavigationType() +
    " may use unvalidated URL. Validate redirect URLs against an allowlist of trusted domains."
