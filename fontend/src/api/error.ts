export class ApiError extends Error {
  constructor(
    public code: string,
    message: string,
    public status = 500,
    public requestId: string = crypto.randomUUID(),
    public details: Record<string, unknown> = {},
    public fieldErrors: { field: string; message: string }[] = [],
  ) {
    super(message);
    this.name = 'ApiError';
  }
}
