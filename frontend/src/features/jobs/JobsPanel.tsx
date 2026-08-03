import { useMemo, useState } from "react";
import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";

import {
  Alert,
  Box,
  Button,
  Chip,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Divider,
  FormControl,
  InputLabel,
  MenuItem,
  Paper,
  Select,
  Stack,
  Typography,
} from "@mui/material";

import {
  Activity,
  Ban,
  CheckCircle2,
  Clock3,
  Eye,
  RefreshCw,
  ServerCog,
  XCircle,
} from "lucide-react";

import { apiRequest, ApiError } from "../../api/http";

type JobRecord = Record<string, unknown>;

interface JobsResponseEnvelope {
  jobs?: JobRecord[];
  items?: JobRecord[];
  results?: JobRecord[];
  data?: JobRecord[] | JobsResponseEnvelope;
}

function normaliseJobs(response: unknown): JobRecord[] {
  if (Array.isArray(response)) {
    return response.filter(
      (item): item is JobRecord =>
        typeof item === "object" &&
        item !== null,
    );
  }

  if (
    response &&
    typeof response === "object"
  ) {
    const record =
      response as JobsResponseEnvelope;

    const candidates = [
      record.jobs,
      record.items,
      record.results,
    ];

    for (const candidate of candidates) {
      if (Array.isArray(candidate)) {
        return candidate.filter(
          (item): item is JobRecord =>
            typeof item === "object" &&
            item !== null,
        );
      }
    }

    if (Array.isArray(record.data)) {
      return record.data.filter(
        (item): item is JobRecord =>
          typeof item === "object" &&
          item !== null,
      );
    }

    if (
      record.data &&
      typeof record.data === "object"
    ) {
      return normaliseJobs(record.data);
    }
  }

  return [];
}

async function fetchJobs(): Promise<JobRecord[]> {
  const response = await apiRequest<unknown>(
    "/jobs",
  );

  return normaliseJobs(response);
}

async function fetchJobHealth(): Promise<unknown> {
  return apiRequest<unknown>("/jobs/health");
}

async function fetchJob(
  jobId: string,
): Promise<JobRecord> {
  return apiRequest<JobRecord>(
    `/jobs/${encodeURIComponent(jobId)}`,
  );
}

async function cancelJob(
  jobId: string,
): Promise<unknown> {
  return apiRequest<unknown>(
    `/jobs/${encodeURIComponent(jobId)}/cancel`,
    {
      method: "POST",
    },
  );
}

function stringValue(
  value: unknown,
  fallback = "—",
): string {
  if (
    value === null ||
    value === undefined ||
    value === ""
  ) {
    return fallback;
  }

  if (typeof value === "string") {
    return value;
  }

  if (
    typeof value === "number" ||
    typeof value === "boolean"
  ) {
    return String(value);
  }

  return JSON.stringify(value);
}

function jobId(job: JobRecord): string {
  return stringValue(
    job.id ??
      job.job_id ??
      job.uuid ??
      job.task_id,
    "unknown",
  );
}

function jobName(job: JobRecord): string {
  return stringValue(
    job.name ??
      job.job_name ??
      job.type ??
      job.job_type ??
      job.task_type,
    "Background job",
  );
}

function jobStatus(job: JobRecord): string {
  return stringValue(
    job.status ??
      job.state ??
      job.job_status,
    "unknown",
  ).toLowerCase();
}

function jobCreatedAt(
  job: JobRecord,
): string | undefined {
  const value =
    job.created_at ??
    job.submitted_at ??
    job.queued_at ??
    job.started_at;

  return typeof value === "string"
    ? value
    : undefined;
}

function jobStartedAt(
  job: JobRecord,
): string | undefined {
  const value =
    job.started_at ??
    job.start_time;

  return typeof value === "string"
    ? value
    : undefined;
}

function jobCompletedAt(
  job: JobRecord,
): string | undefined {
  const value =
    job.completed_at ??
    job.finished_at ??
    job.ended_at ??
    job.end_time;

  return typeof value === "string"
    ? value
    : undefined;
}

function parseTimestamp(
  value?: string,
): number | null {
  if (!value) {
    return null;
  }

  const time = new Date(value).getTime();

  return Number.isNaN(time)
    ? null
    : time;
}

function formatTimestamp(
  value?: string,
): string {
  const time = parseTimestamp(value);

  if (time === null) {
    return "—";
  }

  return new Date(time).toLocaleString();
}

function formatDuration(job: JobRecord): string {
  const start =
    parseTimestamp(jobStartedAt(job)) ??
    parseTimestamp(jobCreatedAt(job));

  if (start === null) {
    return "—";
  }

  const end =
    parseTimestamp(jobCompletedAt(job)) ??
    (isTerminalStatus(jobStatus(job))
      ? start
      : Date.now());

  const totalSeconds = Math.max(
    0,
    Math.floor((end - start) / 1000),
  );

  const hours = Math.floor(
    totalSeconds / 3600,
  );

  const minutes = Math.floor(
    (totalSeconds % 3600) / 60,
  );

  const seconds = totalSeconds % 60;

  if (hours > 0) {
    return `${hours}h ${minutes}m ${seconds}s`;
  }

  if (minutes > 0) {
    return `${minutes}m ${seconds}s`;
  }

  return `${seconds}s`;
}

function isTerminalStatus(
  status: string,
): boolean {
  return [
    "completed",
    "succeeded",
    "success",
    "failed",
    "cancelled",
    "canceled",
    "terminated",
  ].includes(status);
}

function canCancel(status: string): boolean {
  return [
    "queued",
    "pending",
    "running",
    "processing",
    "started",
    "in_progress",
  ].includes(status);
}

function statusColour(
  status: string,
):
  | "default"
  | "primary"
  | "secondary"
  | "error"
  | "info"
  | "success"
  | "warning" {
  if (
    [
      "completed",
      "succeeded",
      "success",
    ].includes(status)
  ) {
    return "success";
  }

  if (
    [
      "failed",
      "error",
      "terminated",
    ].includes(status)
  ) {
    return "error";
  }

  if (
    [
      "running",
      "processing",
      "started",
      "in_progress",
    ].includes(status)
  ) {
    return "primary";
  }

  if (
    [
      "queued",
      "pending",
      "scheduled",
    ].includes(status)
  ) {
    return "warning";
  }

  if (
    ["cancelled", "canceled"].includes(
      status,
    )
  ) {
    return "default";
  }

  return "info";
}

function readableLabel(
  value: string,
): string {
  return value
    .replace(/_/g, " ")
    .replace(/\b\w/g, (character) =>
      character.toUpperCase(),
    );
}

function errorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 0) {
      return (
        "The background-jobs service cannot be reached. " +
        "Confirm that the FastAPI backend is running on port 8000."
      );
    }

    if (error.status === 401) {
      return "Your session has expired.";
    }

    if (error.status === 403) {
      return "Your account cannot access background jobs.";
    }

    return error.message;
  }

  if (error instanceof Error) {
    return error.message;
  }

  return "Background jobs could not be loaded.";
}

function HealthCard({
  health,
  fetching,
}: {
  health: unknown;
  fetching: boolean;
}) {
  let label = "Unknown";
  let colour:
    | "default"
    | "success"
    | "error"
    | "warning" = "default";

  if (
    health &&
    typeof health === "object"
  ) {
    const record =
      health as Record<string, unknown>;

    const value = stringValue(
      record.status ??
        record.health ??
        record.state,
      "unknown",
    ).toLowerCase();

    label = readableLabel(value);

    if (
      [
        "healthy",
        "ok",
        "ready",
        "active",
      ].includes(value)
    ) {
      colour = "success";
    } else if (
      [
        "unhealthy",
        "failed",
        "error",
      ].includes(value)
    ) {
      colour = "error";
    } else {
      colour = "warning";
    }
  }

  return (
    <Paper
      variant="outlined"
      sx={{
        p: 2.5,
        minWidth: 180,
        flex: 1,
      }}
    >
      <Stack
        direction="row"
        spacing={1.5}
        alignItems="center"
      >
        <ServerCog size={22} />

        <Box>
          <Typography
            variant="body2"
            color="text.secondary"
          >
            Worker health
          </Typography>

          <Stack
            direction="row"
            spacing={1}
            alignItems="center"
          >
            <Chip
              label={
                fetching
                  ? "Checking"
                  : label
              }
              color={colour}
              size="small"
            />
          </Stack>
        </Box>
      </Stack>
    </Paper>
  );
}

function SummaryCard({
  label,
  value,
  icon,
}: {
  label: string;
  value: number;
  icon: React.ReactNode;
}) {
  return (
    <Paper
      variant="outlined"
      sx={{
        p: 2.5,
        minWidth: 180,
        flex: 1,
      }}
    >
      <Stack
        direction="row"
        spacing={1.5}
        alignItems="center"
      >
        {icon}

        <Box>
          <Typography
            variant="body2"
            color="text.secondary"
          >
            {label}
          </Typography>

          <Typography variant="h5">
            {value.toLocaleString()}
          </Typography>
        </Box>
      </Stack>
    </Paper>
  );
}

function JobDetailsDialog({
  jobIdValue,
  open,
  onClose,
}: {
  jobIdValue: string | null;
  open: boolean;
  onClose: () => void;
}) {
  const jobQuery = useQuery<JobRecord>({
    queryKey: ["job", jobIdValue],
    queryFn: () => {
      if (!jobIdValue) {
        throw new Error(
          "A job identifier is required.",
        );
      }

      return fetchJob(jobIdValue);
    },
    enabled: open && Boolean(jobIdValue),
    retry: false,
  });

  return (
    <Dialog
      open={open}
      onClose={onClose}
      fullWidth
      maxWidth="md"
    >
      <DialogTitle>
        Job details
      </DialogTitle>

      <DialogContent dividers>
        {jobQuery.isLoading && (
          <Box
            py={5}
            display="grid"
            sx={{ placeItems: "center" }}
          >
            <CircularProgress />
          </Box>
        )}

        {jobQuery.isError && (
          <Alert severity="error">
            {errorMessage(jobQuery.error)}
          </Alert>
        )}

        {jobQuery.data && (
          <Stack spacing={1.5}>
            {Object.entries(
              jobQuery.data,
            ).map(([key, value]) => (
              <Stack
                key={key}
                direction={{
                  xs: "column",
                  sm: "row",
                }}
                spacing={1}
                justifyContent="space-between"
              >
                <Typography
                  variant="body2"
                  color="text.secondary"
                >
                  {readableLabel(key)}
                </Typography>

                <Typography
                  variant="body2"
                  sx={{
                    maxWidth: {
                      xs: "100%",
                      sm: "65%",
                    },
                    overflowWrap: "anywhere",
                    textAlign: {
                      xs: "left",
                      sm: "right",
                    },
                  }}
                >
                  {stringValue(value)}
                </Typography>
              </Stack>
            ))}
          </Stack>
        )}
      </DialogContent>

      <DialogActions>
        <Button onClick={onClose}>
          Close
        </Button>
      </DialogActions>
    </Dialog>
  );
}

export function JobsPanel() {
  const queryClient = useQueryClient();

  const [statusFilter, setStatusFilter] =
    useState("all");

  const [
    selectedJobId,
    setSelectedJobId,
  ] = useState<string | null>(null);

  const jobsQuery = useQuery<JobRecord[]>({
    queryKey: ["jobs"],
    queryFn: fetchJobs,
    staleTime: 5_000,
    refetchInterval: 10_000,
    refetchIntervalInBackground: false,
    retry: (failureCount, error) => {
      if (
        error instanceof ApiError &&
        [401, 403, 404, 422].includes(
          error.status,
        )
      ) {
        return false;
      }

      return failureCount < 2;
    },
  });

  const healthQuery = useQuery({
    queryKey: ["jobs", "health"],
    queryFn: fetchJobHealth,
    staleTime: 15_000,
    refetchInterval: 30_000,
    refetchIntervalInBackground: false,
    retry: false,
  });

  const cancelMutation = useMutation({
    mutationFn: cancelJob,
    onSuccess: async () => {
      await queryClient.invalidateQueries({
        queryKey: ["jobs"],
      });
    },
  });

  const jobs = jobsQuery.data ?? [];

  const statuses = useMemo(
    () =>
      Array.from(
        new Set(
          jobs.map((job) =>
            jobStatus(job),
          ),
        ),
      ).sort(),
    [jobs],
  );

  const filteredJobs = useMemo(
    () =>
      [...jobs]
        .filter(
          (job) =>
            statusFilter === "all" ||
            jobStatus(job) ===
              statusFilter,
        )
        .sort((left, right) => {
          const leftTime =
            parseTimestamp(
              jobCreatedAt(left),
            ) ?? 0;

          const rightTime =
            parseTimestamp(
              jobCreatedAt(right),
            ) ?? 0;

          return rightTime - leftTime;
        }),
    [jobs, statusFilter],
  );

  const runningCount = jobs.filter(
    (job) =>
      [
        "running",
        "processing",
        "started",
        "in_progress",
      ].includes(jobStatus(job)),
  ).length;

  const completedCount = jobs.filter(
    (job) =>
      [
        "completed",
        "succeeded",
        "success",
      ].includes(jobStatus(job)),
  ).length;

  const failedCount = jobs.filter(
    (job) =>
      [
        "failed",
        "error",
        "terminated",
      ].includes(jobStatus(job)),
  ).length;

  if (jobsQuery.isLoading) {
    return (
      <Box
        minHeight={320}
        display="grid"
        sx={{ placeItems: "center" }}
      >
        <Stack
          spacing={2}
          alignItems="center"
        >
          <CircularProgress />

          <Typography color="text.secondary">
            Loading background jobs...
          </Typography>
        </Stack>
      </Box>
    );
  }

  if (jobsQuery.isError) {
    return (
      <Alert
        severity="error"
        action={
          <Button
            color="inherit"
            size="small"
            onClick={() =>
              void jobsQuery.refetch()
            }
          >
            Retry
          </Button>
        }
      >
        {errorMessage(jobsQuery.error)}
      </Alert>
    );
  }

  return (
    <>
      <Stack spacing={3}>
        <Stack
          direction={{
            xs: "column",
            md: "row",
          }}
          spacing={2}
          justifyContent="space-between"
          alignItems={{
            xs: "flex-start",
            md: "center",
          }}
        >
          <Box>
            <Stack
              direction="row"
              spacing={1}
              alignItems="center"
            >
              <Activity size={24} />

              <Typography variant="h5">
                Background jobs
              </Typography>
            </Stack>

            <Typography
              variant="body2"
              color="text.secondary"
              mt={0.5}
            >
              Monitor asynchronous analytics,
              inference and processing tasks.
            </Typography>
          </Box>

          <Button
            variant="outlined"
            startIcon={
              jobsQuery.isFetching ? (
                <CircularProgress size={16} />
              ) : (
                <RefreshCw size={16} />
              )
            }
            disabled={jobsQuery.isFetching}
            onClick={() =>
              void Promise.all([
                jobsQuery.refetch(),
                healthQuery.refetch(),
              ])
            }
          >
            Refresh
          </Button>
        </Stack>

        {cancelMutation.isError && (
          <Alert severity="error">
            {errorMessage(
              cancelMutation.error,
            )}
          </Alert>
        )}

        <Stack
          direction={{
            xs: "column",
            sm: "row",
          }}
          spacing={2}
        >
          <SummaryCard
            label="Total jobs"
            value={jobs.length}
            icon={<Activity size={22} />}
          />

          <SummaryCard
            label="Running"
            value={runningCount}
            icon={<Clock3 size={22} />}
          />

          <SummaryCard
            label="Completed"
            value={completedCount}
            icon={
              <CheckCircle2
                size={22}
                color="#2e7d32"
              />
            }
          />

          <SummaryCard
            label="Failed"
            value={failedCount}
            icon={
              <XCircle
                size={22}
                color="#d32f2f"
              />
            }
          />

          <HealthCard
            health={healthQuery.data}
            fetching={
              healthQuery.isFetching
            }
          />
        </Stack>

        <Paper
          variant="outlined"
          sx={{ p: 2 }}
        >
          <Stack
            direction={{
              xs: "column",
              sm: "row",
            }}
            spacing={2}
            alignItems={{
              xs: "stretch",
              sm: "center",
            }}
          >
            <FormControl
              size="small"
              sx={{ minWidth: 200 }}
            >
              <InputLabel id="job-status-filter-label">
                Status
              </InputLabel>

              <Select
                labelId="job-status-filter-label"
                label="Status"
                value={statusFilter}
                onChange={(event) =>
                  setStatusFilter(
                    event.target.value,
                  )
                }
              >
                <MenuItem value="all">
                  All statuses
                </MenuItem>

                {statuses.map((status) => (
                  <MenuItem
                    key={status}
                    value={status}
                  >
                    {readableLabel(status)}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>

            <Box flex={1} />

            <Typography
              variant="body2"
              color="text.secondary"
            >
              Showing {filteredJobs.length} of{" "}
              {jobs.length}
            </Typography>
          </Stack>
        </Paper>

        {filteredJobs.length === 0 ? (
          <Alert severity="info">
            No background jobs match the
            selected filter.
          </Alert>
        ) : (
          <Stack spacing={1.5}>
            {filteredJobs.map((job) => {
              const id = jobId(job);
              const status =
                jobStatus(job);

              return (
                <Paper
                  key={id}
                  variant="outlined"
                  sx={{ p: 2.5 }}
                >
                  <Stack
                    direction={{
                      xs: "column",
                      md: "row",
                    }}
                    spacing={2}
                    justifyContent="space-between"
                    alignItems={{
                      xs: "flex-start",
                      md: "center",
                    }}
                  >
                    <Box flex={1}>
                      <Stack
                        direction="row"
                        spacing={1}
                        useFlexGap
                        flexWrap="wrap"
                        alignItems="center"
                      >
                        <Typography variant="h6">
                          {jobName(job)}
                        </Typography>

                        <Chip
                          label={readableLabel(
                            status,
                          )}
                          color={statusColour(
                            status,
                          )}
                          size="small"
                        />
                      </Stack>

                      <Divider sx={{ my: 1.5 }} />

                      <Stack
                        direction={{
                          xs: "column",
                          sm: "row",
                        }}
                        spacing={{
                          xs: 0.5,
                          sm: 3,
                        }}
                      >
                        <Typography
                          variant="body2"
                          color="text.secondary"
                        >
                          ID: {id}
                        </Typography>

                        <Typography
                          variant="body2"
                          color="text.secondary"
                        >
                          Created:{" "}
                          {formatTimestamp(
                            jobCreatedAt(job),
                          )}
                        </Typography>

                        <Typography
                          variant="body2"
                          color="text.secondary"
                        >
                          Duration:{" "}
                          {formatDuration(job)}
                        </Typography>
                      </Stack>
                    </Box>

                    <Stack
                      direction="row"
                      spacing={1}
                    >
                      <Button
                        size="small"
                        variant="outlined"
                        startIcon={
                          <Eye size={16} />
                        }
                        onClick={() =>
                          setSelectedJobId(id)
                        }
                      >
                        Details
                      </Button>

                      {canCancel(status) && (
                        <Button
                          size="small"
                          variant="outlined"
                          color="error"
                          startIcon={
                            cancelMutation.isPending ? (
                              <CircularProgress
                                size={14}
                              />
                            ) : (
                              <Ban size={16} />
                            )
                          }
                          disabled={
                            cancelMutation.isPending
                          }
                          onClick={() => {
                            const confirmed =
                              window.confirm(
                                `Cancel job ${id}?`,
                              );

                            if (confirmed) {
                              cancelMutation.mutate(
                                id,
                              );
                            }
                          }}
                        >
                          Cancel
                        </Button>
                      )}
                    </Stack>
                  </Stack>
                </Paper>
              );
            })}
          </Stack>
        )}
      </Stack>

      <JobDetailsDialog
        jobIdValue={selectedJobId}
        open={selectedJobId !== null}
        onClose={() =>
          setSelectedJobId(null)
        }
      />
    </>
  );
}
