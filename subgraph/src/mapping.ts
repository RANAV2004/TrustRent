
export function handleTenancyCreated(event: any): void {
  // Instantiate dynamic template data source for cloned DepositVault
  // DepositVault.create(event.params.vaultAddress);
  // Create and persist Tenancy entity
}

export function handleLeaseSigned(event: any): void {
  // Update Tenancy signing status
}

export function handleDepositLocked(event: any): void {
  // Update deposit locked status
}

export function handleEvidenceRecorded(event: any): void {
  // Create Evidence entity
}

export function handleMoveOutStarted(event: any): void {
  // Update state to MoveOut and record claim deadline
}

export function handleClaimRaised(event: any): void {
  // Create Claim entity and update state to Disputed
}

export function handleClaimAcceptedByTenant(event: any): void {
  // Update state to Refunded
}

export function handleDisputeDecided(event: any): void {
  // Create Decision entity and update state to Refunded
}

export function handleStateChanged(event: any): void {
  // Record StateTransition entity
}
