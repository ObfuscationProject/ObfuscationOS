#ifndef OK_NATIVE_SUPERVISOR_H
#define OK_NATIVE_SUPERVISOR_H

/* Bounded service supervision, authenticated service-only quiescence and
 * PREPARE/quiesce/COMMIT power policy. The kernel owns final platform action. */
int native_supervisor_run(void);

#endif
