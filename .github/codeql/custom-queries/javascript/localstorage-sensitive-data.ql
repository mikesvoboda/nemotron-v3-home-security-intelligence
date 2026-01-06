/**
 * @name Sensitive data in localStorage/sessionStorage
 * @description Detects storage of potentially sensitive data in browser storage
 *              which could be accessed by malicious scripts via XSS.
 * @kind problem
 * @problem.severity warning
 * @security-severity 5.0
 * @precision medium
 * @id js/sensitive-storage
 * @tags security
 *       external/cwe/cwe-922
 */

import javascript

/**
 * A call to localStorage.setItem or sessionStorage.setItem.
 */
class StorageSetItem extends MethodCallExpr {
  string storageType;

  StorageSetItem() {
    exists(PropAccess pa |
      this.getReceiver() = pa and
      (
        pa.getPropertyName() = "localStorage" and storageType = "localStorage"
        or
        pa.getPropertyName() = "sessionStorage" and storageType = "sessionStorage"
      ) and
      this.getMethodName() = "setItem"
    )
    or
    exists(Identifier id |
      this.getReceiver() = id and
      (
        id.getName() = "localStorage" and storageType = "localStorage"
        or
        id.getName() = "sessionStorage" and storageType = "sessionStorage"
      ) and
      this.getMethodName() = "setItem"
    )
  }

  string getStorageType() { result = storageType }

  /**
   * Gets the key being stored.
   */
  Expr getKeyArg() { result = this.getArgument(0) }

  /**
   * Checks if the key name suggests sensitive data.
   */
  predicate hasSensitiveKey() {
    exists(string key |
      key = this.getKeyArg().(StringLiteral).getValue().toLowerCase() and
      (
        key.matches("%password%") or
        key.matches("%token%") or
        key.matches("%secret%") or
        key.matches("%api_key%") or
        key.matches("%apikey%") or
        key.matches("%auth%") or
        key.matches("%credential%") or
        key.matches("%session%") or
        key.matches("%private%") or
        key.matches("%bearer%")
      )
    )
  }
}

from StorageSetItem storage
where storage.hasSensitiveKey()
select storage,
  "Potentially sensitive data stored in " + storage.getStorageType() +
    ". Consider using httpOnly cookies or secure session management instead."
