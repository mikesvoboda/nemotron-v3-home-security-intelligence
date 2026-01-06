/**
 * @name SQL injection in SQLAlchemy raw queries
 * @description Detects potential SQL injection vulnerabilities in SQLAlchemy text() calls
 *              and raw execute() statements that use string formatting or f-strings.
 * @kind problem
 * @problem.severity error
 * @security-severity 9.0
 * @precision high
 * @id py/sqlalchemy-sql-injection
 * @tags security
 *       external/cwe/cwe-089
 */

import python
import semmle.python.dataflow.new.DataFlow
import semmle.python.dataflow.new.TaintTracking
import semmle.python.ApiGraphs

/**
 * A call to SQLAlchemy's text() function with a formatted string.
 */
class SqlAlchemyTextCall extends Call {
  SqlAlchemyTextCall() {
    exists(Attribute attr |
      this.getFunc() = attr and
      attr.getName() = "text"
    )
    or
    exists(Name name |
      this.getFunc() = name and
      name.getId() = "text"
    )
  }

  /**
   * Gets the SQL string argument passed to text().
   */
  Expr getSqlArg() { result = this.getArg(0) }
}

/**
 * A formatted string (f-string) that may contain user input.
 */
class FormattedSqlString extends Expr {
  FormattedSqlString() {
    this instanceof JoinedStr
    or
    exists(BinaryExpr be |
      this = be and
      be.getOp() instanceof Mod
    )
    or
    exists(Call c |
      this = c and
      c.getFunc().(Attribute).getName() = "format"
    )
  }
}

from SqlAlchemyTextCall textCall, FormattedSqlString formattedStr
where textCall.getSqlArg() = formattedStr
select textCall,
  "Potential SQL injection: SQLAlchemy text() called with formatted string. Use parameterized queries with bindparams() instead."
