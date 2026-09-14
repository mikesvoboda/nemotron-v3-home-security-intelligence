/**
 * @name Unsafe file path operations
 * @description Detects file operations using paths that may be controlled by user input
 *              without proper validation, leading to path traversal vulnerabilities.
 * @kind problem
 * @problem.severity error
 * @security-severity 8.0
 * @precision medium
 * @id py/unsafe-file-path
 * @tags security
 *       external/cwe/cwe-022
 */

import python
import semmle.python.dataflow.new.DataFlow
import semmle.python.dataflow.new.TaintTracking

/**
 * A call to file-related functions that accept a path argument.
 */
class FileOperation extends Call {
  string operationType;

  FileOperation() {
    exists(Name name |
      this.getFunc() = name and
      name.getId() = "open" and
      operationType = "open"
    )
    or
    exists(Attribute attr |
      this.getFunc() = attr and
      (
        attr.getName() = "read_text" and operationType = "read_text"
        or
        attr.getName() = "read_bytes" and operationType = "read_bytes"
        or
        attr.getName() = "write_text" and operationType = "write_text"
        or
        attr.getName() = "write_bytes" and operationType = "write_bytes"
        or
        attr.getName() = "unlink" and operationType = "unlink"
        or
        attr.getName() = "rmdir" and operationType = "rmdir"
        or
        attr.getName() = "rename" and operationType = "rename"
        or
        attr.getName() = "remove" and operationType = "remove"
      )
    )
  }

  string getOperationType() { result = operationType }

  Expr getPathArg() {
    operationType = "open" and result = this.getArg(0)
    or
    operationType != "open" and result = this.getFunc().(Attribute).getObject()
  }
}

/**
 * A FastAPI path parameter that could contain malicious input.
 */
class FastApiPathParameter extends Parameter {
  FastApiPathParameter() {
    exists(Function f, Decorator d |
      this = f.getAnArg() and
      d = f.getADecorator() and
      exists(Call c |
        d.getValue() = c and
        exists(StringLiteral sl |
          c.getArg(0) = sl and
          sl.getText().matches("%{" + this.getName() + "}%")
        )
      )
    )
  }
}

/**
 * An f-string that uses a variable for file paths.
 */
class FormattedPathString extends JoinedStr {
  FormattedPathString() {
    // Contains at least one formatted value (not just literal strings)
    exists(FormattedValue fv | fv.getParent+() = this)
  }
}

from FileOperation fileOp, FormattedPathString formattedPath
where fileOp.getPathArg() = formattedPath
select fileOp,
  "File operation '" + fileOp.getOperationType() +
    "' uses formatted string for path. Validate path does not contain '..' and resolves within expected directory."
