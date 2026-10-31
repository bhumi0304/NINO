import React from "react";

import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";


const CLASS_ORDER = [
  "FORWARD",
  "LEFT",
  "RIGHT",
  "UP",
  "DOWN",
];


function percent(value) {
  const number = Number(value || 0);

  return `${(number * 100).toFixed(1)}%`;
}


function MatrixCell({
  value,
  maxValue,
  diagonal,
}) {
  const numeric = Number(value || 0);

  const strength =
    maxValue > 0
      ? numeric / maxValue
      : 0;

  const alpha = Math.min(
    0.82,
    0.1 + strength * 0.62
  );

  return (
    <div
      title={`${numeric} samples`}
      style={{
        minHeight: "46px",
        display: "grid",
        placeItems: "center",
        borderRadius: "9px",
        fontWeight: 800,
        fontSize: "12px",

        color: diagonal
          ? "#0f5f43"
          : "#5f6d68",

        background: diagonal
          ? `rgba(31, 143, 99, ${alpha})`
          : `rgba(
              193,
              59,
              59,
              ${Math.min(
                0.36,
                0.06 + strength * 0.28
              )}
            )`,

        border:
          "1px solid rgba(26, 56, 45, 0.08)",
      }}
    >
      {numeric}
    </div>
  );
}


function ModelEvaluationPanel({
  modelInfo,
}) {
  const info = modelInfo || {};

  const available = Boolean(
    info.evaluation_available
  );

  const classes =
    Array.isArray(info.classes) &&
    info.classes.length > 0
      ? info.classes
      : CLASS_ORDER;

  const matrix =
    Array.isArray(
      info.confusion_matrix
    )
      ? info.confusion_matrix
      : [];

  const perClass =
    info.per_class || {};

  const featureImportance =
    Array.isArray(
      info.feature_importance
    )
      ? info.feature_importance
      : [];

  const matrixValues =
    matrix
      .flat()
      .map(
        (value) =>
          Number(value || 0)
      );

  const matrixMax =
    matrixValues.length > 0
      ? Math.max(
          ...matrixValues
        )
      : 0;


  if (!available) {
    return (
      <section className="panel">
        <span className="kicker">
          MODEL EVALUATION
        </span>

        <h3>
          Evaluation data unavailable
        </h3>

        <p
          style={{
            margin: "7px 0 0",
            color: "#64756f",
            fontSize: "12px",
            lineHeight: 1.6,
          }}
        >
          Run the NINO
          head-direction evaluation
          script to generate the
          confusion matrix, class
          metrics and feature
          importance.
        </p>
      </section>
    );
  }


  const chartData =
    featureImportance
      .slice(0, 10)
      .map(
        (item) => ({
          feature: String(
            item.feature || ""
          ).replaceAll(
            "_",
            " "
          ),

          importance: Number(
            item.importance || 0
          ),
        })
      );


  return (
    <div
      style={{
        display: "grid",
        gap: "14px",
      }}
    >
      {/* =========================================
          GENERALIZATION RESULT
      ========================================== */}

      <section className="panel">
        <div
          style={{
            display: "flex",
            alignItems:
              "flex-start",
            justifyContent:
              "space-between",
            gap: "18px",
            flexWrap: "wrap",
          }}
        >
          <div>
            <span className="kicker">
              GENERALIZATION RESULT
            </span>

            <h3
              style={{
                marginBottom:
                  "5px",
              }}
            >
              Held-out
              cross-session validation
            </h3>

            <p
              style={{
                margin: 0,
                maxWidth: "650px",
                color: "#64756f",
                fontSize: "12px",
                lineHeight: 1.6,
              }}
            >
              Sessions were separated
              during evaluation so the
              model was tested on a
              collection session not
              used for that training
              fold. This is still not
              unseen-person validation.
            </p>
          </div>


          <div
            style={{
              display: "grid",

              gridTemplateColumns:
                "repeat(3, minmax(90px, 1fr))",

              gap: "9px",

              minWidth: "320px",
            }}
          >
            <div
              style={{
                padding: "12px",

                borderRadius:
                  "12px",

                background:
                  "#f2f7f4",
              }}
            >
              <span
                style={{
                  display:
                    "block",

                  color:
                    "#71817b",

                  fontSize:
                    "10px",
                }}
              >
                Accuracy
              </span>

              <strong
                style={{
                  display:
                    "block",

                  marginTop:
                    "4px",

                  fontSize:
                    "20px",

                  color:
                    "#147652",
                }}
              >
                {percent(
                  info
                    .cross_session_accuracy
                )}
              </strong>
            </div>


            <div
              style={{
                padding: "12px",

                borderRadius:
                  "12px",

                background:
                  "#f2f7f4",
              }}
            >
              <span
                style={{
                  display:
                    "block",

                  color:
                    "#71817b",

                  fontSize:
                    "10px",
                }}
              >
                Macro F1
              </span>

              <strong
                style={{
                  display:
                    "block",

                  marginTop:
                    "4px",

                  fontSize:
                    "20px",

                  color:
                    "#147652",
                }}
              >
                {percent(
                  info.macro_f1
                )}
              </strong>
            </div>


            <div
              style={{
                padding: "12px",

                borderRadius:
                  "12px",

                background:
                  "#f2f7f4",
              }}
            >
              <span
                style={{
                  display:
                    "block",

                  color:
                    "#71817b",

                  fontSize:
                    "10px",
                }}
              >
                Accuracy std
              </span>

              <strong
                style={{
                  display:
                    "block",

                  marginTop:
                    "4px",

                  fontSize:
                    "20px",

                  color:
                    "#147652",
                }}
              >
                {percent(
                  info
                    .session_accuracy_std
                )}
              </strong>
            </div>
          </div>
        </div>
      </section>


      {/* =========================================
          CONFUSION MATRIX
      ========================================== */}

      <section className="panel">
        <span className="kicker">
          CONFUSION MATRIX
        </span>

        <h3>
          Final-model class behavior
        </h3>

        <p
          style={{
            margin:
              "4px 0 14px",

            color:
              "#64756f",

            fontSize:
              "12px",

            lineHeight:
              1.55,
          }}
        >
          Rows are actual directions
          and columns are model
          predictions. Green diagonal
          cells are correct
          classifications.

          This matrix comes from the
          final model evaluated on the
          complete dataset and should
          not be presented as held-out
          accuracy.
        </p>


        {matrix.length > 0 ? (
          <div
            style={{
              overflowX:
                "auto",
            }}
          >
            <div
              style={{
                minWidth:
                  "640px",

                display:
                  "grid",

                gridTemplateColumns:
                  `110px repeat(
                    ${classes.length},
                    minmax(82px, 1fr)
                  )`,

                gap: "6px",

                alignItems:
                  "stretch",
              }}
            >
              <div />


              {classes.map(
                (label) => (
                  <div
                    key={
                      `header-${label}`
                    }

                    style={{
                      display:
                        "grid",

                      placeItems:
                        "center",

                      minHeight:
                        "34px",

                      color:
                        "#60716b",

                      fontSize:
                        "10px",

                      fontWeight:
                        800,
                    }}
                  >
                    PRED {label}
                  </div>
                )
              )}


              {classes.map(
                (
                  rowLabel,
                  rowIndex
                ) => (
                  <React.Fragment
                    key={
                      `row-${rowLabel}`
                    }
                  >
                    <div
                      style={{
                        display:
                          "flex",

                        alignItems:
                          "center",

                        padding:
                          "0 8px",

                        color:
                          "#60716b",

                        fontSize:
                          "10px",

                        fontWeight:
                          800,
                      }}
                    >
                      TRUE {rowLabel}
                    </div>


                    {classes.map(
                      (
                        columnLabel,
                        columnIndex
                      ) => (
                        <MatrixCell
                          key={
                            `${rowLabel}-${columnLabel}`
                          }

                          value={
                            matrix[
                              rowIndex
                            ]?.[
                              columnIndex
                            ] ?? 0
                          }

                          maxValue={
                            matrixMax
                          }

                          diagonal={
                            rowIndex ===
                            columnIndex
                          }
                        />
                      )
                    )}
                  </React.Fragment>
                )
              )}
            </div>
          </div>
        ) : (
          <div className="empty-state">
            Confusion matrix was
            not returned by the API.
          </div>
        )}
      </section>


      {/* =========================================
          PER CLASS PERFORMANCE
      ========================================== */}

      <section className="panel">
        <span className="kicker">
          PER-CLASS PERFORMANCE
        </span>

        <h3>
          Precision, recall and F1
        </h3>


        <div
          style={{
            marginTop:
              "13px",

            overflowX:
              "auto",
          }}
        >
          <table
            style={{
              width:
                "100%",

              minWidth:
                "620px",

              borderCollapse:
                "collapse",

              fontSize:
                "12px",
            }}
          >
            <thead>
              <tr>
                {[
                  "Class",
                  "Precision",
                  "Recall",
                  "F1",
                  "Samples",
                ].map(
                  (heading) => (
                    <th
                      key={
                        heading
                      }

                      style={{
                        padding:
                          "10px 12px",

                        textAlign:
                          "left",

                        color:
                          "#64756f",

                        borderBottom:
                          "1px solid #e6ece9",

                        fontSize:
                          "10px",

                        letterSpacing:
                          ".04em",
                      }}
                    >
                      {heading}
                    </th>
                  )
                )}
              </tr>
            </thead>


            <tbody>
              {classes.map(
                (label) => {
                  const metrics =
                    perClass[
                      label
                    ] || {};

                  return (
                    <tr
                      key={
                        label
                      }
                    >
                      <td
                        style={{
                          padding:
                            "11px 12px",

                          borderBottom:
                            "1px solid #eef2f0",

                          fontWeight:
                            800,
                        }}
                      >
                        {label}
                      </td>


                      <td
                        style={{
                          padding:
                            "11px 12px",

                          borderBottom:
                            "1px solid #eef2f0",
                        }}
                      >
                        {percent(
                          metrics
                            .precision
                        )}
                      </td>


                      <td
                        style={{
                          padding:
                            "11px 12px",

                          borderBottom:
                            "1px solid #eef2f0",
                        }}
                      >
                        {percent(
                          metrics
                            .recall
                        )}
                      </td>


                      <td
                        style={{
                          padding:
                            "11px 12px",

                          borderBottom:
                            "1px solid #eef2f0",
                        }}
                      >
                        {percent(
                          metrics.f1
                        )}
                      </td>


                      <td
                        style={{
                          padding:
                            "11px 12px",

                          borderBottom:
                            "1px solid #eef2f0",
                        }}
                      >
                        {
                          metrics.support
                          ?? 0
                        }
                      </td>
                    </tr>
                  );
                }
              )}
            </tbody>
          </table>
        </div>
      </section>


      {/* =========================================
          FEATURE IMPORTANCE
      ========================================== */}

      <section className="panel">
        <span className="kicker">
          RANDOM FOREST
          EXPLAINABILITY
        </span>

        <h3>
          Top 10 feature
          importances
        </h3>

        <p
          style={{
            margin:
              "4px 0 14px",

            color:
              "#64756f",

            fontSize:
              "12px",

            lineHeight:
              1.55,
          }}
        >
          Importance indicates how
          strongly each aligned
          facial-geometry feature
          contributes to splits
          across the Random Forest.

          It does not imply causation.
        </p>


        {chartData.length > 0 ? (
          <ResponsiveContainer
            width="100%"
            height={340}
          >
            <BarChart
              data={
                chartData
              }

              layout="vertical"

              margin={{
                top: 4,
                right: 20,
                bottom: 4,
                left: 25,
              }}
            >
              <CartesianGrid
                strokeDasharray=
                  "3 3"

                horizontal={
                  false
                }
              />


              <XAxis
                type="number"

                tickLine={
                  false
                }

                axisLine={
                  false
                }

                tickFormatter={
                  (value) =>
                    Number(
                      value
                    ).toFixed(
                      2
                    )
                }
              />


              <YAxis
                type="category"

                dataKey=
                  "feature"

                width={150}

                tickLine={
                  false
                }

                axisLine={
                  false
                }

                tick={{
                  fontSize:
                    10,
                }}
              />


              <Tooltip
                formatter={
                  (value) => [
                    Number(
                      value
                    ).toFixed(
                      5
                    ),

                    "Importance",
                  ]
                }
              />


              <Bar
                dataKey=
                  "importance"

                fill=
                  "#1f8f63"

                radius={[
                  0,
                  6,
                  6,
                  0,
                ]}
              />
            </BarChart>
          </ResponsiveContainer>
        ) : (
          <div className="empty-state">
            Feature-importance
            data was not returned
            by the API.
          </div>
        )}
      </section>


      {/* =========================================
          VALIDATION LIMITATION
      ========================================== */}

      <section
        className="panel"

        style={{
          border:
            "1px solid #eadfbf",

          background:
            "#fffdf7",
        }}
      >
        <span className="kicker">
          VALIDATION LIMITATION
        </span>

        <h3>
          Controlled academic
          prototype
        </h3>

        <p
          style={{
            margin:
              "6px 0 0",

            color:
              "#6b6251",

            fontSize:
              "12px",

            lineHeight:
              1.65,
          }}
        >
          NINO currently uses 1,322
          samples from three controlled
          collection sessions.

          The model has cross-session
          validation, but it has not
          yet been validated across a
          sufficiently large group of
          unseen drivers, lighting
          conditions, camera positions,
          eyewear types, or real-road
          environments.
        </p>
      </section>
    </div>
  );
}


export default ModelEvaluationPanel;