/**
 * @name React dangerouslySetInnerHTML usage
 * @description Detects usage of dangerouslySetInnerHTML which can lead to XSS vulnerabilities
 *              if the HTML content is not properly sanitized.
 * @kind problem
 * @problem.severity warning
 * @security-severity 7.0
 * @precision high
 * @id js/react-dangerous-html
 * @tags security
 *       external/cwe/cwe-079
 */

import javascript

/**
 * A JSX attribute setting dangerouslySetInnerHTML.
 */
class DangerousHtmlAttribute extends JSXAttribute {
  DangerousHtmlAttribute() { this.getName() = "dangerouslySetInnerHTML" }
}

from DangerousHtmlAttribute attr
select attr,
  "Usage of dangerouslySetInnerHTML detected. Ensure content is properly sanitized with DOMPurify or similar library to prevent XSS attacks."
