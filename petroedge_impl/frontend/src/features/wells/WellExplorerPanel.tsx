import {
  useMemo,
  useState,
} from "react";

import {
  useMutation,
  useQuery,
} from "@tanstack/react-query";

import {
  Alert,
  Box,
  Button,
  Chip,
  CircularProgress,
  FormControl,
  InputLabel,
  MenuItem,
  Paper,
  Select,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Typography,
} from "@mui/material";

import {
  Activity,
  BarChart3,
  FlaskConical,
  RefreshCw,
} from "lucide-react";

import { ApiError } from "../../api/http";

import {
  normaliseCollection,
  readNumber,
  readString,
} from "../../api/normalise";

import type {
  AnalyticsResult,
  SampleAnalysisRequest,
  WellLogSample,
  WellSummary,
} from "../../api/types";

import {
  analyseSample,
  fetchWell,
  fetchWellAlerts,
  fetchWellLogs,
  fetchWells,
} from "./api";

type UnknownRecord =
  Record<string, unknown>;

function asRecord(
  value: unknown,
): UnknownRecord {
  if (
    value &&
    typeof value === "object"
  ) {
    return value as UnknownRecord;
  }

  return {};
}

function getWellId(
  well: WellSummary,
): string {
  return readString(
    asRecord(well),
    [
      "well_id",
      "id",
      "name",
      "well_name",
    ],
    "",
  );
}

function getWellName(
  well: WellSummary,
): string {
  return readString(
    asRecord(well),
    [
      "name",
      "well_name",
      "well_id",
      "id",
    ],
    "Unnamed well",
  );
}

function getDepth(
  sample: WellLogSample,
): number | null {
  return readNumber(
    asRecord(sample),
    [
      "depth",
      "md",
      "measured_depth",
      "tvd",
      "tvdss",
    ],
  );
}


function displayNumber(
  value: number | null,
  digits = 3,
): string {
  return value === null
    ? "—"
    : value.toFixed(digits);
}

function errorMessage(
  error: unknown,
): string {
  if (error instanceof ApiError) {
    if (error.status === 0) {
      return (
        "The PetroEdge API cannot be reached. " +
        "Confirm that FastAPI is running on port 8000."
      );
    }

    if (error.status === 401) {
      return "Your session has expired.";
    }

    if (error.status === 403) {
      return "You do not have permission to access this well.";
    }

    return error.message;
  }

  if (error instanceof Error) {
    return error.message;
  }

  return "The request could not be completed.";
}

function createAnalysisPayload(
  sample: WellLogSample,
  wellId: string,
): SampleAnalysisRequest {
  const source = asRecord(sample);

  const payload = {
    ...source,
    well_id:
      typeof source.well_id === "string" &&
      source.well_id.trim()
        ? source.well_id
        : wellId,
  };

  /*
   * Well-log rows are normalised dynamically because field names may
   * differ between imported LAS datasets. The runtime payload is still
   * validated by the FastAPI request schema.
   */
  return payload as unknown as SampleAnalysisRequest;
}

function AnalysisPanel({
  result,
}: {
  result: AnalyticsResult | null;
}) {
  if (!result) {
    return (
      <Alert severity="info">
        Select a log sample and run the
        analysis to view the predicted
        petrophysical interpretation.
      </Alert>
    );
  }

  const record = asRecord(result);

  const fields = [
    [
      "Lithology",
      readString(
        record,
        [
          "lithology",
          "predicted_lithology",
          "facies",
        ],
      ),
    ],
    [
      "Porosity",
      displayNumber(
        readNumber(
          record,
          [
            "porosity",
            "predicted_porosity",
            "phi",
          ],
        ),
      ),
    ],
    [
      "Water saturation",
      displayNumber(
        readNumber(
          record,
          [
            "water_saturation",
            "sw",
            "predicted_sw",
          ],
        ),
      ),
    ],
    [
      "Hydrocarbon probability",
      displayNumber(
        readNumber(
          record,
          [
            "hydrocarbon_probability",
            "hc_probability",
            "probability",
          ],
        ),
      ),
    ],
    [
      "Reservoir quality",
      readString(
        record,
        [
          "reservoir_quality",
          "quality",
          "classification",
        ],
      ),
    ],
    [
      "Confidence",
      displayNumber(
        readNumber(
          record,
          [
            "confidence",
            "confidence_score",
          ],
        ),
      ),
    ],
  ];

  return (
    <Stack spacing={1.5}>
      {fields.map(
        ([label, value]) => (
          <Stack
            key={label}
            direction="row"
            justifyContent="space-between"
            spacing={2}
          >
            <Typography
              variant="body2"
              color="text.secondary"
            >
              {label}
            </Typography>

            <Typography
              variant="body2"
              fontWeight={600}
            >
              {value}
            </Typography>
          </Stack>
        ),
      )}
    </Stack>
  );
}

export function WellExplorerPanel() {
  const [selectedWellId, setSelectedWellId] =
    useState("");

  const [
    selectedSample,
    setSelectedSample,
  ] = useState<WellLogSample | null>(
    null,
  );

  const wellsQuery = useQuery({
    queryKey: ["wells"],
    queryFn: fetchWells,
    staleTime: 60_000,
  });

  const wells =
    useMemo(
      () =>
        normaliseCollection<WellSummary>(
          wellsQuery.data,
          ["wells"],
        ),
      [wellsQuery.data],
    );

  const activeWellId =
    selectedWellId ||
    (wells.length > 0
      ? getWellId(wells[0])
      : "");

  const wellQuery = useQuery({
    queryKey: ["well", activeWellId],
    queryFn: () =>
      fetchWell(activeWellId),
    enabled: Boolean(activeWellId),
    staleTime: 60_000,
  });

  const logsQuery = useQuery({
    queryKey: [
      "well",
      activeWellId,
      "logs",
    ],
    queryFn: () =>
      fetchWellLogs(activeWellId),
    enabled: Boolean(activeWellId),
    staleTime: 15_000,
  });

  const alertsQuery = useQuery({
    queryKey: [
      "well",
      activeWellId,
      "alerts",
    ],
    queryFn: () =>
      fetchWellAlerts(activeWellId),
    enabled: Boolean(activeWellId),
    staleTime: 15_000,
    refetchInterval: 30_000,
  });

  const analysisMutation =
    useMutation({
      mutationFn: ({
        sample,
        wellId,
      }: {
        sample: WellLogSample;
        wellId: string;
      }) =>
        analyseSample(
          createAnalysisPayload(
            sample,
            wellId,
          ),
        ),
    });

  const logs =
    useMemo(
      () =>
        normaliseCollection<WellLogSample>(
          logsQuery.data,
          [
            "logs",
            "samples",
            "well_logs",
          ],
        ),
      [logsQuery.data],
    );

  const alerts =
    useMemo(
      () =>
        normaliseCollection<UnknownRecord>(
          alertsQuery.data,
          ["alerts"],
        ),
      [alertsQuery.data],
    );

  const visibleLogs =
    useMemo(
      () => logs.slice(0, 500),
      [logs],
    );

  const selectedWell =
    wells.find(
      (well) =>
        getWellId(well) ===
        activeWellId,
    ) ?? null;

  if (wellsQuery.isLoading) {
    return (
      <Box
        minHeight={360}
        display="grid"
        sx={{ placeItems: "center" }}
      >
        <CircularProgress />
      </Box>
    );
  }

  if (wellsQuery.isError) {
    return (
      <Alert severity="error">
        {errorMessage(
          wellsQuery.error,
        )}
      </Alert>
    );
  }

  return (
    <Stack spacing={3}>
      <Stack
        direction={{
          xs: "column",
          md: "row",
        }}
        justifyContent="space-between"
        alignItems={{
          xs: "stretch",
          md: "center",
        }}
        spacing={2}
      >
        <Box>
          <Stack
            direction="row"
            spacing={1}
            alignItems="center"
          >
            <BarChart3 size={24} />

            <Typography variant="h5">
              Well Log Explorer
            </Typography>
          </Stack>

          <Typography
            variant="body2"
            color="text.secondary"
            mt={0.5}
          >
            Inspect log curves and run
            sample-level reservoir analytics.
          </Typography>
        </Box>

        <Button
          variant="outlined"
          startIcon={
            logsQuery.isFetching ? (
              <CircularProgress size={16} />
            ) : (
              <RefreshCw size={16} />
            )
          }
          onClick={() => {
            void wellQuery.refetch();
            void logsQuery.refetch();
            void alertsQuery.refetch();
          }}
        >
          Refresh
        </Button>
      </Stack>

      <Paper
        variant="outlined"
        sx={{ p: 2.5 }}
      >
        <Stack
          direction={{
            xs: "column",
            md: "row",
          }}
          spacing={2}
          alignItems={{
            xs: "stretch",
            md: "center",
          }}
        >
          <FormControl
            size="small"
            sx={{ minWidth: 260 }}
          >
            <InputLabel id="well-selector-label">
              Well
            </InputLabel>

            <Select
              labelId="well-selector-label"
              label="Well"
              value={activeWellId}
              onChange={(event) => {
                setSelectedWellId(
                  event.target.value,
                );

                setSelectedSample(null);
                analysisMutation.reset();
              }}
            >
              {wells.map((well) => {
                const id =
                  getWellId(well);

                return (
                  <MenuItem
                    key={id}
                    value={id}
                  >
                    {getWellName(well)}
                  </MenuItem>
                );
              })}
            </Select>
          </FormControl>

          {selectedWell && (
            <Chip
              label={getWellName(
                selectedWell,
              )}
              color="primary"
              variant="outlined"
            />
          )}

          <Chip
            label={`${logs.length.toLocaleString()} samples`}
            variant="outlined"
          />

          <Chip
            label={`${alerts.length.toLocaleString()} alerts`}
            color={
              alerts.length > 0
                ? "warning"
                : "default"
            }
            variant="outlined"
          />
        </Stack>
      </Paper>

      {(logsQuery.isError ||
        alertsQuery.isError) && (
        <Alert severity="error">
          {errorMessage(
            logsQuery.error ??
              alertsQuery.error,
          )}
        </Alert>
      )}

      <Stack
        direction={{
          xs: "column",
          lg: "row",
        }}
        spacing={3}
        alignItems="stretch"
      >
        <Paper
          variant="outlined"
          sx={{
            flex: 2,
            minWidth: 0,
          }}
        >
          <Box p={2.5}>
            <Stack
              direction="row"
              spacing={1}
              alignItems="center"
            >
              <Activity size={20} />

              <Typography variant="h6">
                Log samples
              </Typography>
            </Stack>

            {logs.length > 500 && (
              <Typography
                variant="caption"
                color="text.secondary"
              >
                Displaying the first 500 of{" "}
                {logs.length.toLocaleString()}{" "}
                samples.
              </Typography>
            )}
          </Box>

          {logsQuery.isLoading ? (
            <Box
              minHeight={300}
              display="grid"
              sx={{ placeItems: "center" }}
            >
              <CircularProgress />
            </Box>
          ) : visibleLogs.length === 0 ? (
            <Alert severity="info">
              No log samples are available
              for this well.
            </Alert>
          ) : (
            <TableContainer
              sx={{ maxHeight: 560 }}
            >
              <Table
                stickyHeader
                size="small"
              >
                <TableHead>
                  <TableRow>
                    <TableCell>
                      Depth
                    </TableCell>

                    <TableCell>
                      GR
                    </TableCell>

                    <TableCell>
                      Resistivity
                    </TableCell>

                    <TableCell>
                      RHOB
                    </TableCell>

                    <TableCell>
                      NPHI
                    </TableCell>

                    <TableCell>
                      Sonic
                    </TableCell>

                    <TableCell align="right">
                      Action
                    </TableCell>
                  </TableRow>
                </TableHead>

                <TableBody>
                  {visibleLogs.map(
                    (sample, index) => {
                      const record =
                        asRecord(sample);

                      const depth =
                        getDepth(sample);

                      const selected =
                        selectedSample ===
                        sample;

                      return (
                        <TableRow
                          key={`${depth ?? "sample"}-${index}`}
                          hover
                          selected={selected}
                          onClick={() =>
                            setSelectedSample(
                              sample,
                            )
                          }
                          sx={{
                            cursor: "pointer",
                          }}
                        >
                          <TableCell>
                            {displayNumber(
                              depth,
                              2,
                            )}
                          </TableCell>

                          <TableCell>
                            {displayNumber(
                              readNumber(
                                record,
                                [
                                  "gr",
                                  "gamma_ray",
                                  "GR",
                                ],
                              ),
                              2,
                            )}
                          </TableCell>

                          <TableCell>
                            {displayNumber(
                              readNumber(
                                record,
                                [
                                  "resistivity",
                                  "rt",
                                  "ild",
                                  "RT",
                                ],
                              ),
                              3,
                            )}
                          </TableCell>

                          <TableCell>
                            {displayNumber(
                              readNumber(
                                record,
                                [
                                  "rhob",
                                  "density",
                                  "RHOB",
                                ],
                              ),
                              3,
                            )}
                          </TableCell>

                          <TableCell>
                            {displayNumber(
                              readNumber(
                                record,
                                [
                                  "nphi",
                                  "neutron_porosity",
                                  "NPHI",
                                ],
                              ),
                              3,
                            )}
                          </TableCell>

                          <TableCell>
                            {displayNumber(
                              readNumber(
                                record,
                                [
                                  "dt",
                                  "sonic",
                                  "DT",
                                ],
                              ),
                              2,
                            )}
                          </TableCell>

                          <TableCell align="right">
                            <Button
                              size="small"
                              startIcon={
                                <FlaskConical
                                  size={15}
                                />
                              }
                              onClick={(
                                event,
                              ) => {
                                event.stopPropagation();

                                setSelectedSample(
                                  sample,
                                );

                                analysisMutation.mutate(
                                  {
                                    sample,
                                    wellId:
                                      activeWellId,
                                  },
                                );
                              }}
                            >
                              Analyse
                            </Button>
                          </TableCell>
                        </TableRow>
                      );
                    },
                  )}
                </TableBody>
              </Table>
            </TableContainer>
          )}
        </Paper>

        <Paper
          variant="outlined"
          sx={{
            flex: 1,
            minWidth: {
              xs: 0,
              lg: 340,
            },
            p: 2.5,
          }}
        >
          <Stack spacing={2}>
            <Stack
              direction="row"
              spacing={1}
              alignItems="center"
            >
              <FlaskConical size={20} />

              <Typography variant="h6">
                Sample analysis
              </Typography>
            </Stack>

            {selectedSample && (
              <Typography
                variant="body2"
                color="text.secondary"
              >
                Selected depth:{" "}
                {displayNumber(
                  getDepth(
                    selectedSample,
                  ),
                  2,
                )}
              </Typography>
            )}

            {analysisMutation.isPending && (
              <Box
                py={4}
                display="grid"
                sx={{
                  placeItems: "center",
                }}
              >
                <CircularProgress />
              </Box>
            )}

            {analysisMutation.isError && (
              <Alert severity="error">
                {errorMessage(
                  analysisMutation.error,
                )}
              </Alert>
            )}

            {!analysisMutation.isPending && (
              <AnalysisPanel
                result={
                  (analysisMutation.data ??
                    null) as AnalyticsResult | null
                }
              />
            )}

            {selectedSample &&
              !analysisMutation.isPending && (
                <Button
                  variant="contained"
                  startIcon={
                    <FlaskConical
                      size={16}
                    />
                  }
                  onClick={() =>
                    analysisMutation.mutate(
                      {
                        sample:
                          selectedSample,
                        wellId:
                          activeWellId,
                      },
                    )
                  }
                >
                  Run analysis
                </Button>
              )}
          </Stack>
        </Paper>
      </Stack>

      <Paper
        variant="outlined"
        sx={{ p: 2.5 }}
      >
        <Typography
          variant="h6"
          mb={2}
        >
          Well alerts
        </Typography>

        {alerts.length === 0 ? (
          <Alert severity="success">
            No alerts are currently
            associated with this well.
          </Alert>
        ) : (
          <Stack spacing={1.5}>
            {alerts.map(
              (alert, index) => {
                const severity =
                  readString(
                    alert,
                    ["severity"],
                    "info",
                  ).toLowerCase();

                return (
                  <Alert
                    key={
                      readString(
                        alert,
                        [
                          "id",
                          "alert_id",
                        ],
                        String(index),
                      )
                    }
                    severity={
                      severity === "critical" ||
                      severity === "high"
                        ? "error"
                        : severity ===
                            "warning" ||
                          severity ===
                            "medium"
                        ? "warning"
                        : "info"
                    }
                  >
                    <Typography
                      variant="body2"
                      fontWeight={600}
                    >
                      {readString(
                        alert,
                        [
                          "title",
                          "name",
                          "message",
                        ],
                        "Well alert",
                      )}
                    </Typography>

                    <Typography
                      variant="body2"
                    >
                      {readString(
                        alert,
                        [
                          "message",
                          "description",
                          "recommendation",
                        ],
                        "",
                      )}
                    </Typography>
                  </Alert>
                );
              },
            )}
          </Stack>
        )}
      </Paper>
    </Stack>
  );
}
