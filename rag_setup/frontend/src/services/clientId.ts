const CLIENT_ID_STORAGE_KEY =
  "cis-controls-client-id-v1"

function createClientId(): string {
  return crypto.randomUUID()
}

export function getOrCreateClientId():
  string {
  const existingClientId =
    window.localStorage.getItem(
      CLIENT_ID_STORAGE_KEY,
    )

  if (
    existingClientId
    && existingClientId.length >= 8
  ) {
    return existingClientId
  }

  const newClientId =
    createClientId()

  window.localStorage.setItem(
    CLIENT_ID_STORAGE_KEY,
    newClientId,
  )

  return newClientId
}
