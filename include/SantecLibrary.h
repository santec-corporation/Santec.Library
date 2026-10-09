#ifndef SANTEC_LIBRARY_H
#define SANTEC_LIBRARY_H

#include <stdint.h>
#include <stdbool.h>

/*
 * If no features are explicitly opted in, enable everything (backward compatible).
 * To build a minimal library, define one or more SANTEC_INCLUDE_* symbols before
 * including this header:
 *   #define SANTEC_INCLUDE_TSL
 *   #define SANTEC_INCLUDE_MPM
 *   #include "SantecLibrary.h"
 */
#if !defined(SANTEC_INCLUDE_TSL) && !defined(SANTEC_INCLUDE_MPM) && \
    !defined(SANTEC_INCLUDE_OPM) && !defined(SANTEC_INCLUDE_PCU) && \
    !defined(SANTEC_INCLUDE_LMS) && !defined(SANTEC_INCLUDE_SWEEP_PIPELINE) && \
    !defined(SANTEC_INCLUDE_OPM_NETWORK) && !defined(SANTEC_INCLUDE_PDL_CALCULATION)
#define SANTEC_INCLUDE_TSL
#define SANTEC_INCLUDE_MPM
#define SANTEC_INCLUDE_OPM
#define SANTEC_INCLUDE_PCU
#define SANTEC_INCLUDE_LMS
#define SANTEC_INCLUDE_SWEEP_PIPELINE
#define SANTEC_INCLUDE_OPM_NETWORK
#define SANTEC_INCLUDE_PDL_CALCULATION
#endif

#ifdef __cplusplus
extern "C" {
#endif

/* -------------------------------------------------------------------------
 * Enumerations
 * ------------------------------------------------------------------------- */

/**
 * Log event level (mirrors Serilog.Events.LogEventLevel).
 */
typedef enum LogEventLevel
{
    LogEventLevel_Verbose     = 0,
    LogEventLevel_Debug       = 1,
    LogEventLevel_Information = 2,
    LogEventLevel_Warning     = 3,
    LogEventLevel_Error       = 4,
    LogEventLevel_Fatal       = 5
} LogEventLevel;

/**
 * Nominal wavelength band for OPM-150.
 *
 * Use SetTSLWavelength() to set an arbitrary wavelength in nanometers.
 *
 * The managed enum is byte-backed, so the C++ form fixes the underlying type. C
 * cannot express that, so C gets an integer typedef and the same constants; the
 * width matters because a wider argument would leave the upper bits of the
 * register undefined. The member list is written once and expanded in both
 * branches so they cannot drift apart.
 */
#define SANTEC_NOMINAL_WAVELENGTH_MEMBERS \
    NominalWavelength_Unknown = 0xFF, \
    NominalWavelength_Wl850   = 0, \
    NominalWavelength_Wl980   = 1, \
    NominalWavelength_Wl1300  = 2, \
    NominalWavelength_Wl1310  = 3, \
    NominalWavelength_Wl1490  = 4, \
    NominalWavelength_Wl1550  = 5, \
    NominalWavelength_Wl1625  = 6, \
    NominalWavelength_Wl1650  = 7

#ifdef __cplusplus
typedef enum NominalWavelength : uint8_t
{
    SANTEC_NOMINAL_WAVELENGTH_MEMBERS
} NominalWavelength;
#else
typedef uint8_t NominalWavelength;
enum
{
    SANTEC_NOMINAL_WAVELENGTH_MEMBERS
};
#endif
#undef SANTEC_NOMINAL_WAVELENGTH_MEMBERS

/**
 * Polarization state.
 *
 * The managed enum is int-backed, so this is a 32-bit type: declaring it as a
 * byte would put garbage in the upper bits of the argument register.
 *
 * C++ keeps the short member names (LVP, LHP, ...) for compatibility with
 * existing code. C gets prefixed names, because an unscoped enum would put
 * "Unknown", "LVP" and "RCP" into the global namespace of every translation unit
 * that includes this header.
 */
#ifdef __cplusplus
typedef enum PolarizationState : int32_t
{
    Unknown = 0, /** Unspecified, e.g. arbitrary waveplate angles (PCU-200) */
    LVP  = 1, /** Linear Vertical Polarization   */
    LHP  = 2, /** Linear Horizontal Polarization  */
    LP45 = 3, /** Linear 45-Degree Polarization   */
    LN45 = 4, /** Linear -45-Degree Polarization  */
    RCP  = 5, /** Right-Hand Circular Polarization */
    LCP  = 6  /** Left-Hand Circular Polarization  */
} PolarizationState;
#else
typedef int32_t PolarizationState;
enum
{
    PolarizationState_Unknown = 0, /** Unspecified, e.g. arbitrary waveplate angles (PCU-200) */
    PolarizationState_LVP  = 1, /** Linear Vertical Polarization   */
    PolarizationState_LHP  = 2, /** Linear Horizontal Polarization  */
    PolarizationState_LP45 = 3, /** Linear 45-Degree Polarization   */
    PolarizationState_LN45 = 4, /** Linear -45-Degree Polarization  */
    PolarizationState_RCP  = 5, /** Right-Hand Circular Polarization */
    PolarizationState_LCP  = 6  /** Left-Hand Circular Polarization  */
};
#endif

/* -------------------------------------------------------------------------
 * Connection configuration
 * ------------------------------------------------------------------------- */

/**
 * Connection configuration (mirrors Santec.Library.Shared.ConnectionConfig).
 */
typedef struct ConnectionConfig
{
    const char* Type;         /** Connection type ("VISA", "FTDI", "DAQ", "LAN"). */
    const char* VendorName;   /** Vendor name. */
    const char* ProductName;  /** Product name. */
    const char* Address;      /** Address (VISA resource string, IP endpoint, etc.). */
    int32_t     ProductNumber; /** Product number. */
    const char* SerialNumber; /** Serial number. */
    const char* FirmwareVersion; /** Firmware version. */
} ConnectionConfig;

/* -------------------------------------------------------------------------
 * Logging
 * ------------------------------------------------------------------------- */

/**
 * Sets the minimum log level threshold.
 *
 * @param level  Only events at this level or higher are logged.
 */
void SetLogLevel(LogEventLevel level);

/**
 * Enables debug-level logging.
 */
void EnableDebug(void);

/**
 * Enables verbose-level logging.
 */
void EnableVerbose(void);

/* -------------------------------------------------------------------------
 * Device discovery
 * ------------------------------------------------------------------------- */

/**
 * Returns the number of connected devices.
 *
 * @return  Device count, or 0 if none are detected.
 */
int32_t GetDeviceNum(void);

/**
 * Writes device connection configurations into a caller-supplied buffer.
 *
 * Pass the count from GetDeviceNum() as the capacity. At most `capacity`
 * entries are written and never more than the device count, so a device that
 * appears between the two calls cannot overrun the buffer.
 *
 * The strings inside the written structures are allocated by the library: call
 * FreeConnectionConfigs() with the returned count before reusing or freeing the
 * buffer. The buffer itself belongs to the caller.
 *
 * @param devices   Buffer that receives the ConnectionConfig array.
 * @param capacity  Number of ConnectionConfig entries the buffer can hold.
 * @return          Number of entries written.
 */
int32_t GetDevices(void* devices, int32_t capacity);

/**
 * Releases the strings that GetDevices() wrote into a caller's buffer.
 *
 * Does not free the buffer itself. Safe to call with a null pointer or a
 * non-positive count.
 *
 * @param devices  Buffer filled by GetDevices().
 * @param count    Entry count returned by GetDevices().
 */
void FreeConnectionConfigs(ConnectionConfig* devices, int32_t count);

/* -------------------------------------------------------------------------
 * Connection management
 * ------------------------------------------------------------------------- */

/**
 * Connects to a device.
 *
 * @param devPtr  ConnectionConfig for the target device.
 * @return        true on success.
 */
bool SetConnection(void* devPtr);

/**
 * Connects to a TSL, Power Meter, and optionally a DAQ device.
 *
 * When @p spuPtr is NULL, only the TSL and Power Meter connections are made.
 *
 * @param tslPtr  ConnectionConfig for the TSL device.
 * @param mpmPtr  ConnectionConfig for the Power Meter.
 * @param spuPtr  ConnectionConfig for the DAQ device, or NULL.
 * @return        true when all required connections succeed.
 */
bool SetConnections(void* tslPtr, void* mpmPtr, void* spuPtr);

/**
 * Disconnects and releases all resources.
 */
void Disconnect(void);

#ifdef SANTEC_INCLUDE_SWEEP_PIPELINE
/* -------------------------------------------------------------------------
 * Sweep / Measurement Pipeline
 * ------------------------------------------------------------------------- */

/**
 * Resets all parameter builders to their defaults.
 *
 * Call before starting a new measurement to clear any prior configuration.
 */
void ResetParameters(void);

/**
 * Enables high-resolution mode on all parameter builders.
 */
void EnableHighResolution(void);

/**
 * Sets sweep parameters for the measurement system.
 *
 * Applies to MPM, OPM, and LMS power meters.
 *
 * @param startWavelength  Start wavelength (nm).
 * @param stopWavelength   Stop wavelength (nm).
 * @param stepWidth        Wavelength step (nm).
 * @param power            Optical power (mW).
 * @param speed            Sweep speed (nm/s).
 * @param cycles           Number of sweep cycles.
 * @param delay            Inter-cycle delay (ms).
 */
void SetSweepParameters(double startWavelength, double stopWavelength,
                        double stepWidth, double power, double speed,
                        int32_t cycles, int32_t delay);

/**
 * Sets the range profile for an MPM channel.
 *
 * @param moduleNumber   Zero-based module index.
 * @param channelNumber  Zero-based channel index.
 * @param range          Range profile (0 for auto-range).
 */
void SetMPMChannel(int32_t moduleNumber, int32_t channelNumber, uint8_t range);

/**
 * Sets the range profile for an OPM module.
 *
 * @param moduleNumber  Module identifier.
 * @param range         Range profile (0 for auto-range).
 */
void SetOPMModule(int32_t moduleNumber, uint8_t range);

/**
 * Sets the range profile for an Agilent LMS channel.
 *
 * @param moduleNumber   Zero-based module index.
 * @param channelNumber  Zero-based channel index.
 * @param range          Range profile (0 for auto-range).
 */
void SetAgilentLMSChannel(int32_t moduleNumber, int32_t channelNumber, uint8_t range);

/**
 * Runs a reference scan on the connected instrument.
 *
 * The library allocates the returned buffer. Free it with FreeArrayData().
 *
 * @param dataPtr     Receives the data buffer.
 * @param dataLength  Receives the buffer size in bytes.
 * @return            true on success.
 */
bool ReferenceScan(uint8_t** dataPtr, int32_t* dataLength);

/**
 * Runs a measurement scan on the connected instrument.
 *
 * The library allocates the returned buffer. Free it with FreeArrayData().
 *
 * @param dataPtr     Receives the data buffer.
 * @param dataLength  Receives the buffer size in bytes.
 * @return            true on success.
 */
bool MeasurementScan(uint8_t** dataPtr, int32_t* dataLength);

/**
 * Validates device parameters.
 *
 * Uses the first TSL in the connection together with the first MPM, OPM-200 or
 * LMS. A connection holding only an OPM-150 cannot sweep, and is reported as an
 * error: read that instrument with ReadOPMPower() or ReadOPMAllChannels().
 *
 * @return  Error message string (UTF-8), or NULL when validation passes.
 *          Free non-NULL results with FreeString().
 */
char* ValidateParameters(void);

/**
 * Imports reference data from a file.
 *
 * @param fileNamePtr  Path to the file (null-terminated).
 */
void ImportReferenceData(const char* fileNamePtr);

/**
 * Exports the last reference scan to IL format.
 *
 * Legacy: the destination comes from the auto-save configuration, which this
 * library never sets, so there is no defined output location. Use
 * ExportReferenceDataTo() instead.
 */
void ExportReferenceData(void);

/**
 * Exports the last reference scan to CSV, one file per result.
 *
 * Writes "<directory>\<baseName>_<channel>.csv" for each result, so the output
 * names are predictable. The directory must already exist. The call reports
 * nothing: check that the files appeared.
 *
 * @param directoryPtr  Null-terminated UTF-8 directory path.
 * @param baseNamePtr   Null-terminated UTF-8 file name stem.
 */
void ExportReferenceDataTo(const char* directoryPtr, const char* baseNamePtr);

/**
 * Exports the last measurement scan to IL format.
 *
 * Legacy: the destination comes from the auto-save configuration, which this
 * library never sets, so there is no defined output location. Use
 * ExportMeasurementDataTo() instead.
 */
void ExportMeasurementData(void);

/**
 * Exports the last measurement scan to IL CSV, one file per result.
 *
 * Writes "<directory>\<baseName>_<channel>.csv" for each result, with raw data
 * included. The directory must already exist. The call reports nothing: check
 * that the files appeared.
 *
 * @param directoryPtr  Null-terminated UTF-8 directory path.
 * @param baseNamePtr   Null-terminated UTF-8 file name stem.
 */
void ExportMeasurementDataTo(const char* directoryPtr, const char* baseNamePtr);
#endif /* SANTEC_INCLUDE_SWEEP_PIPELINE */

#ifdef SANTEC_INCLUDE_TSL
/* -------------------------------------------------------------------------
 * TSL - Basic Control
 * ------------------------------------------------------------------------- */

/**
 * Reads the TSL output power.
 *
 * @return  Power in dBm or mW depending on the active power mode,
 *          or NaN if no device is connected.
 */
double GetTSLPower(void);

/**
 * Sets the TSL output power.
 *
 * Interpreted as mW or dBm based on the active power mode.
 * Use GetTSLPowerMode() / SetTSLPowerMode() to switch.
 *
 * @param power  Desired power level.
 */
void SetTSLPower(double power);

/**
 * Reads the TSL wavelength.
 *
 * @return  Wavelength in nanometers, or NaN if no device is connected.
 */
double GetTSLWavelength(void);

/**
 * Sets the TSL wavelength.
 *
 * @param wavelength  Wavelength (nm).
 */
void SetTSLWavelength(double wavelength);

/**
 * Reads the TSL optical frequency.
 *
 * @return  Frequency in terahertz, or NaN if no device is connected.
 */
double GetTSLFrequency(void);

/**
 * Sets the TSL optical frequency.
 *
 * @param frequency  Frequency (THz).
 */
void SetTSLFrequency(double frequency);

/* -------------------------------------------------------------------------
 * TSL - Fine Tuning
 * ------------------------------------------------------------------------- */

/**
 * Reads the fine-tuning offset.
 *
 * @return  Offset in picometers, or NaN if no device is connected.
 */
double GetTSLFineTuning(void);

/**
 * Sets the fine-tuning offset.
 *
 * @param value  Offset (pm).
 */
void SetTSLFineTuning(double value);

/**
 * Resets fine tuning to zero.
 */
void StopTSLFineTuning(void);

/* -------------------------------------------------------------------------
 * TSL - Sweep Control
 *
 * A connection that reports TSL2 exposes StartTSL2Sweep and StopTSL2Sweep only.
 * Pause and restart are prohibited on ITSL2, so these two entry points address
 * a TSL rather than a TSL2 device.
 * ------------------------------------------------------------------------- */

/**
 * Checks whether the TSL is busy.
 *
 * @param waitTime  Maximum wait (ms).
 * @return          1 if busy, 0 otherwise.
 */
int32_t CheckTSLBusy(int32_t waitTime);

/**
 * Starts a wavelength sweep.
 */
void StartTSLSweep(void);

/**
 * Stops the active sweep.
 */
void StopTSLSweep(void);

/**
 * Pauses the active sweep.
 *
 * Prohibited on ITSL2. Use it on a TSL only.
 */
void PauseTSLSweep(void);

/**
 * Restarts a paused sweep.
 *
 * Prohibited on ITSL2. Use it on a TSL only.
 */
void RestartTSLSweep(void);

/**
 * Repeats the last sweep.
 */
void RepeatTSLSweep(void);

/**
 * Returns the number of completed sweep repetitions.
 *
 * @return  Sweep count, or 0 if no device is connected.
 */
int32_t GetTSLSweepCount(void);

/**
 * Reads the sweep status.
 *
 * @return  Sweep status enum value, or 0 if no device is connected.
 */
int32_t GetTSLSweepStatus(void);

/**
 * Sets the sweep status.
 *
 * @param value  Sweep status enum value.
 */
void SetTSLSweepStatus(int32_t value);

/**
 * Reads the sweep mode.
 *
 * @return  Sweep mode enum value, or 0 if no device is connected.
 */
int32_t GetTSLSweepMode(void);

/**
 * Sets the sweep mode.
 *
 * @param value  Sweep mode enum value.
 */
void SetTSLSweepMode(int32_t value);

/**
 * Reads the sweep start mode.
 *
 * @return  Sweep start mode enum value, or 0 if no device is connected.
 */
int32_t GetTSLSweepStartMode(void);

/**
 * Sets the sweep start mode.
 *
 * @param value  Sweep start mode enum value.
 */
void SetTSLSweepStartMode(int32_t value);

/**
 * Returns the number of data points per sweep.
 *
 * @return  Data point count, or 0 if no device is connected.
 */
int32_t GetTSLDataPoints(void);

/* -------------------------------------------------------------------------
 * TSL - Sweep Parameters
 * ------------------------------------------------------------------------- */

/**
 * Reads the sweep start wavelength.
 *
 * @return  Wavelength (nm), or NaN if no device is connected.
 */
double GetTSLSweepStartWavelength(void);

/**
 * Sets the sweep start wavelength.
 *
 * @param value  Wavelength (nm).
 */
void SetTSLSweepStartWavelength(double value);

/**
 * Reads the sweep stop wavelength.
 *
 * @return  Wavelength (nm), or NaN if no device is connected.
 */
double GetTSLSweepStopWavelength(void);

/**
 * Sets the sweep stop wavelength.
 *
 * @param value  Wavelength (nm).
 */
void SetTSLSweepStopWavelength(double value);

/**
 * Reads the sweep start frequency.
 *
 * @return  Frequency (THz), or NaN if no device is connected.
 */
double GetTSLSweepStartFrequency(void);

/**
 * Sets the sweep start frequency.
 *
 * @param value  Frequency (THz).
 */
void SetTSLSweepStartFrequency(double value);

/**
 * Reads the sweep stop frequency.
 *
 * @return  Frequency (THz), or NaN if no device is connected.
 */
double GetTSLSweepStopFrequency(void);

/**
 * Sets the sweep stop frequency.
 *
 * @param value  Frequency (THz).
 */
void SetTSLSweepStopFrequency(double value);

/**
 * Reads the wavelength step size.
 *
 * @return  Step size (nm), or NaN if no device is connected.
 */
double GetTSLWavelengthStep(void);

/**
 * Sets the wavelength step size.
 *
 * @param value  Step size (nm).
 */
void SetTSLWavelengthStep(double value);

/**
 * Reads the frequency step size.
 *
 * @return  Step size (THz), or NaN if no device is connected.
 */
double GetTSLFrequencyStep(void);

/**
 * Sets the frequency step size.
 *
 * @param value  Step size (THz).
 */
void SetTSLFrequencyStep(double value);

/**
 * Computes the minimum valid trigger step for a given sweep speed.
 *
 * @param speed                Sweep speed (nm/s).
 * @param triggerOutputSource  Trigger output source enum value.
 * @return                     Minimum trigger step (nm),
 *                             or NaN if no device is connected.
 */
double CalculateTSLMinimumTriggerStep(double speed, int32_t triggerOutputSource);

/**
 * Computes the sweep speed from start and stop wavelengths.
 *
 * @param startWavelength  Start wavelength (nm).
 * @param stopWavelength   Stop wavelength (nm).
 * @return                 Sweep speed (nm/s),
 *                         or NaN if no device is connected.
 */
double GetTSLSweepSpeed(double startWavelength, double stopWavelength);

/**
 * Sets the sweep speed.
 *
 * @param value  Sweep speed (nm/s).
 */
void SetTSLSweepSpeed(double value);

/**
 * Reads the sweep delay.
 *
 * @return  Delay (ms), or NaN if no device is connected.
 */
double GetTSLSweepDelay(void);

/**
 * Sets the sweep delay.
 *
 * @param value  Delay (ms).
 */
void SetTSLSweepDelay(double value);

/**
 * Reads the sweep dwell time.
 *
 * @return  Dwell time (ms), or NaN if no device is connected.
 */
double GetTSLSweepDwell(void);

/**
 * Sets the sweep dwell time.
 *
 * @param value  Dwell time (ms).
 */
void SetTSLSweepDwell(double value);

/**
 * Reads the sweep cycle count.
 *
 * @return  Number of cycles, or 0 if no device is connected.
 */
int32_t GetTSLSweepCycle(void);

/**
 * Sets the sweep cycle count.
 *
 * @param value  Number of cycles.
 */
void SetTSLSweepCycle(int32_t value);

/* -------------------------------------------------------------------------
 * TSL - Trigger Control
 * ------------------------------------------------------------------------- */

/**
 * Sends a software trigger.
 */
void SetTSLSoftwareTrigger(void);

/**
 * Reads the trigger input mode.
 *
 * @return  Trigger input mode enum value, or 0 if no device is connected.
 */
int32_t GetTSLTriggerInputMode(void);

/**
 * Sets the trigger input mode.
 *
 * @param value  Trigger input mode enum value.
 */
void SetTSLTriggerInputMode(int32_t value);

/**
 * Reads the trigger output mode.
 *
 * @return  Trigger output mode enum value, or 0 if no device is connected.
 */
int32_t GetTSLTriggerOutputMode(void);

/**
 * Sets the trigger output mode.
 *
 * @param value  Trigger output mode enum value.
 */
void SetTSLTriggerOutputMode(int32_t value);

/**
 * Reads the trigger step size.
 *
 * @return  Step size (nm), or NaN if no device is connected.
 */
double GetTSLTriggerStep(void);

/**
 * Sets the trigger step size.
 *
 * @param value  Step size (nm).
 */
void SetTSLTriggerStep(double value);

/* -------------------------------------------------------------------------
 * TSL - Power & ATT Control
 * ------------------------------------------------------------------------- */

/**
 * Reads the power mode.
 *
 * @return  Power mode enum value, or 0 if no device is connected.
 */
int32_t GetTSLPowerMode(void);

/**
 * Sets the power mode.
 *
 * @param value  Power mode enum value.
 */
void SetTSLPowerMode(int32_t value);

/**
 * Reads the power unit.
 *
 * @return  Power unit enum value, or 0 if no device is connected.
 */
int32_t GetTSLPowerUnit(void);

/**
 * Sets the power unit.
 *
 * @param value  Power unit enum value.
 */
void SetTSLPowerUnit(int32_t value);

/**
 * Reads the monitor power.
 *
 * @return  Monitor power value, or NaN if no device is connected.
 */
double GetTSLMonitorPower(void);

/**
 * Zeroes the power data.
 */
void CompensateTSLPowerData(void);

/**
 * Reads the attenuator value.
 *
 * @return  ATT value (dB), or NaN if no device is connected.
 */
double GetTSLATT(void);

/**
 * Sets the attenuator value.
 *
 * @param value  ATT value (dB).
 */
void SetTSLATT(double value);

/* -------------------------------------------------------------------------
 * TSL - APC Power Limits
 * ------------------------------------------------------------------------- */

/**
 * Reads the minimum APC power.
 *
 * @return  Minimum APC power, or NaN if no device is connected.
 */
double GetTSLMinimumAPCPower(void);

/**
 * Reads the maximum APC power.
 *
 * @return  Maximum APC power, or NaN if no device is connected.
 */
double GetTSLMaximumAPCPower(void);

/**
 * Reads the minimum APC power in milliwatts.
 *
 * @return  Minimum APC power (mW), or NaN if no device is connected.
 */
double GetTSLMinimumAPCPower_mW(void);

/**
 * Reads the maximum APC power in milliwatts.
 *
 * @return  Maximum APC power (mW), or NaN if no device is connected.
 */
double GetTSLMaximumAPCPower_mW(void);

/**
 * Reads the minimum APC power in dBm.
 *
 * @return  Minimum APC power (dBm), or NaN if no device is connected.
 */
double GetTSLMinimumAPCPower_dBm(void);

/**
 * Reads the maximum APC power in dBm.
 *
 * @return  Maximum APC power (dBm), or NaN if no device is connected.
 */
double GetTSLMaximumAPCPower_dBm(void);

/* -------------------------------------------------------------------------
 * TSL - Capability Queries
 * ------------------------------------------------------------------------- */

/**
 * Reads the minimum supported wavelength.
 *
 * @return  Wavelength (nm), or NaN if no device is connected.
 */
double GetTSLMinimumWavelength(void);

/**
 * Reads the maximum supported wavelength.
 *
 * @return  Wavelength (nm), or NaN if no device is connected.
 */
double GetTSLMaximumWavelength(void);

/**
 * Reads the minimum supported frequency.
 *
 * @return  Frequency (THz), or NaN if no device is connected.
 */
double GetTSLMinimumFrequency(void);

/**
 * Reads the maximum supported frequency.
 *
 * @return  Frequency (THz), or NaN if no device is connected.
 */
double GetTSLMaximumFrequency(void);

/**
 * Reads the minimum sweep speed.
 *
 * @return  Speed (nm/s), or NaN if no device is connected.
 */
double GetTSLMinimumSpeed(void);

/**
 * Reads the maximum sweep speed.
 *
 * @return  Speed (nm/s), or NaN if no device is connected.
 */
double GetTSLMaximumSpeed(void);

/**
 * Reads the minimum attenuator value.
 *
 * @return  ATT value (dB), or NaN if no device is connected.
 */
double GetTSLMinimumATT(void);

/**
 * Reads the maximum attenuator value.
 *
 * @return  ATT value (dB), or NaN if no device is connected.
 */
double GetTSLMaximumATT(void);

/* -------------------------------------------------------------------------
 * TSL - Status & Configuration
 * ------------------------------------------------------------------------- */

/**
 * Reads the wavelength unit setting.
 *
 * @return  Wavelength unit enum value, or 0 if no device is connected.
 */
int32_t GetTSLWavelengthUnit(void);

/**
 * Sets the wavelength unit.
 *
 * @param value  Wavelength unit enum value.
 */
void SetTSLWavelengthUnit(int32_t value);

/**
 * Reads the laser diode status.
 *
 * @return  LD status enum value, or 0 if no device is connected.
 */
int32_t GetTSLLDStatus(void);

/**
 * Sets the laser diode status.
 *
 * @param value  LD status enum value.
 */
void SetTSLLDStatus(int32_t value);

/**
 * Reads the shutter status.
 *
 * @return  Shutter status enum value, or 0 if no device is connected.
 */
int32_t GetTSLShutterStatus(void);

/**
 * Sets the shutter status.
 *
 * @param value  Shutter status enum value.
 */
void SetTSLShutterStatus(int32_t value);

/**
 * Reads the amplitude modulation status.
 *
 * @return  AM status enum value, or 0 if no device is connected.
 */
int32_t GetTSLAMStatus(void);

/**
 * Sets the amplitude modulation status.
 *
 * @param value  AM status enum value.
 */
void SetTSLAMStatus(int32_t value);

/**
 * Reads the coherence control setting.
 *
 * @return  Coherence control enum value, or 0 if no device is connected.
 */
int32_t GetTSLCoherenceControl(void);

/**
 * Sets the coherence control setting.
 *
 * @param value  Coherence control enum value.
 */
void SetTSLCoherenceControl(int32_t value);

/**
 * Reads the command mode.
 *
 * @return  Command mode enum value, or 0 if no device is connected.
 */
int32_t GetTSLCommandMode(void);

/**
 * Sets the command mode.
 *
 * @param value  Command mode enum value.
 */
void SetTSLCommandMode(int32_t value);

/**
 * Reads the general status word.
 *
 * @return  Status value, or 0 if no device is connected.
 */
int32_t GetTSLStatus(void);

/**
 * Reads the system error state.
 */
void GetTSLSystemError(void);

/**
 * Reads the logging data as floats.
 */
void GetTSLLoggingDataF(void);

/**
 * Reads the logging data.
 */
void GetTSLLoggingData(void);

/**
 * Reads the product type.
 *
 * @return  Product type enum value, or 0 if no device is connected.
 */
int32_t GetTSLProductType(void);

/**
 * Reads the model identifier.
 *
 * @return  Model enum value, or 0 if no device is connected.
 */
int32_t GetTSLModel(void);

/**
 * Waits until the sweep reaches one of the given statuses.
 *
 * @param waitTime  Milliseconds to wait before giving up.
 * @param status    Status to wait for.
 * @param notEqual  Non-zero to wait until the status is anything but @p status.
 * @return          1 when the status was reached, 0 on timeout or when no device is connected.
 */
int32_t WaitTSLForSweepStatus(int32_t waitTime, int32_t status, int32_t notEqual);

/**
 * Reads whether the instrument understands the LLP command set.
 *
 * @return  1 if LLP compatible, 0 otherwise or when no device is connected.
 */
int32_t GetTSLIsLLPCompatible(void);

/**
 * Reads the active command format.
 *
 * @return  Command format enum value, or 0 if no device is connected.
 */
int32_t GetTSLCommandFormat(void);

/* -------------------------------------------------------------------------
 * TSL2 - Laser Source
 *
 * TSL2 inherits the laser-source and sweepable-laser-source contracts, so these
 * duplicate the TSL entry points above for a connection that reports TSL2.
 * ------------------------------------------------------------------------- */

/**
 * Reads the wavelength (TSL2).
 *
 * @return  Wavelength in nanometers, or NaN if no device is connected.
 */
double GetTSL2Wavelength(void);

/**
 * Sets the wavelength (TSL2).
 *
 * @param value  Wavelength in nanometers.
 */
void SetTSL2Wavelength(double value);

/**
 * Reads the optical frequency (TSL2).
 *
 * @return  Frequency in terahertz, or NaN if no device is connected.
 */
double GetTSL2Frequency(void);

/**
 * Sets the optical frequency (TSL2).
 *
 * @param value  Frequency in terahertz.
 */
void SetTSL2Frequency(double value);

/**
 * Reads the output power (TSL2).
 *
 * @return  Power in mW or dBm depending on the power mode, or NaN if no device is connected.
 */
double GetTSL2Power(void);

/**
 * Sets the output power (TSL2).
 *
 * @param value  Power in mW or dBm depending on the power mode.
 */
void SetTSL2Power(double value);

/**
 * Reads the power unit (TSL2).
 *
 * @return  Power unit enum value, or 0 if no device is connected.
 */
int32_t GetTSL2PowerUnit(void);

/**
 * Sets the power unit (TSL2).
 *
 * @param value  Power unit enum value.
 */
void SetTSL2PowerUnit(int32_t value);

/**
 * Reads the laser diode status (TSL2).
 *
 * @return  LD status enum value, or 0 if no device is connected.
 */
int32_t GetTSL2LDStatus(void);

/**
 * Sets the laser diode status (TSL2).
 *
 * @param value  LD status enum value.
 */
void SetTSL2LDStatus(int32_t value);

/**
 * Reads whether the instrument understands the LLP command set (TSL2).
 *
 * @return  1 if LLP compatible, 0 otherwise or when no device is connected.
 */
int32_t GetTSL2IsLLPCompatible(void);

/**
 * Reads the active command format (TSL2).
 *
 * @return  Command format enum value, or 0 if no device is connected.
 */
int32_t GetTSL2CommandFormat(void);

/**
 * Reads the sweep speed (TSL2).
 *
 * @return  Sweep speed in nanometers per second, or NaN if no device is connected.
 */
double GetTSL2SweepSpeed(void);

/**
 * Sets the sweep speed (TSL2).
 *
 * @param value  Sweep speed in nanometers per second.
 */
void SetTSL2SweepSpeed(double value);

/**
 * Reads the sweep mode (TSL2).
 *
 * @return  Sweep mode enum value, or 0 if no device is connected.
 */
int32_t GetTSL2SweepMode(void);

/**
 * Sets the sweep mode (TSL2).
 *
 * @param value  Sweep mode enum value.
 */
void SetTSL2SweepMode(int32_t value);

/**
 * Reads the sweep status (TSL2).
 *
 * @return  Sweep status enum value, or 0 if no device is connected.
 */
int32_t GetTSL2SweepStatus(void);

/**
 * Starts a sweep (TSL2).
 *
 * A TSL2 device cannot pause or restart a sweep. PauseTSLSweep and
 * RestartTSLSweep are prohibited on ITSL2 and have no TSL2 counterpart.
 */
void StartTSL2Sweep(void);

/**
 * Stops the sweep (TSL2).
 */
void StopTSL2Sweep(void);

/* -------------------------------------------------------------------------
 * TSL2 - Advanced Control
 * ------------------------------------------------------------------------- */

/**
 * Reads the power logging data as floats (TSL2).
 */
void GetTSL2PowerLoggingDataF(void);

/**
 * Reads the power logging data (TSL2).
 */
void GetTSL2PowerLoggingData(void);

/**
 * Reads the trigger output source (TSL2).
 *
 * @return  Trigger output source enum value, or 0 if no device is connected.
 */
int32_t GetTSL2TriggerOutputSource(void);

/**
 * Sets the trigger output source (TSL2).
 *
 * @param value  Trigger output source enum value.
 */
void SetTSL2TriggerOutputSource(int32_t value);

/**
 * Reads the trigger pass-through setting (TSL2).
 *
 * @return  1 if enabled, 0 otherwise.
 */
int32_t GetTSL2TriggerPassThrough(void);

/**
 * Sets trigger pass-through (TSL2).
 *
 * @param value  1 to enable, 0 to disable.
 */
void SetTSL2TriggerPassThrough(int32_t value);

/**
 * Reads the AM source (TSL2).
 *
 * @return  AM source enum value, or 0 if no device is connected.
 */
int32_t GetTSL2AMSource(void);

/**
 * Sets the AM source (TSL2).
 *
 * @param value  AM source enum value.
 */
void SetTSL2AMSource(int32_t value);

/**
 * Reads the input trigger polarity (TSL2).
 *
 * @return  Input trigger polarity enum value, or 0 if no device is connected.
 */
int32_t GetTSL2InputTriggerPolarity(void);

/**
 * Sets the input trigger polarity (TSL2).
 *
 * @param value  Input trigger polarity enum value.
 */
void SetTSL2InputTriggerPolarity(int32_t value);

/**
 * Reads the output trigger polarity (TSL2).
 *
 * @return  Output trigger polarity enum value, or 0 if no device is connected.
 */
int32_t GetTSL2OutputTriggerPolarity(void);

/**
 * Sets the output trigger polarity (TSL2).
 *
 * @param value  Output trigger polarity enum value.
 */
void SetTSL2OutputTriggerPolarity(int32_t value);

/**
 * Reads alert information (TSL2).
 */
void GetTSL2Alert(void);

/**
 * Reads the firmware version (TSL2).
 */
void GetTSL2Version(void);

/**
 * Reads the product code (TSL2).
 */
void GetTSL2ProductCode(void);

/**
 * Reads the product type (TSL2).
 *
 * @return  Product type enum value, or 0 if no device is connected.
 */
int32_t GetTSL2ProductType(void);

/**
 * Reads the model identifier (TSL2).
 *
 * @return  Model enum value, or 0 if no device is connected.
 */
int32_t GetTSL2Model(void);
#endif /* SANTEC_INCLUDE_TSL */

#ifdef SANTEC_INCLUDE_MPM
/* -------------------------------------------------------------------------
 * MPM control
 * ------------------------------------------------------------------------- */

/**
 * Reads the measured power for all channels of an MPM module.
 *
 * The library allocates the returned array. Free it with FreeArrayData().
 *
 * @param moduleNumber   Zero-based module index.
 * @param powersPtr      Receives the power array.
 * @param powersLength   Receives the element count.
 * @return               true on success.
 */
bool GetMPMModulePower(int32_t moduleNumber, double** powersPtr, int32_t* powersLength);

/**
 * Reads the power from a single MPM channel.
 *
 * @param moduleNumber   Zero-based module index.
 * @param channelNumber  Zero-based channel index.
 * @return               Power reading, or NaN if not found.
 */
double GetMPMPower(int32_t moduleNumber, int32_t channelNumber);

/**
 * Reads info for the connected MPM and its modules.
 *
 * The library allocates the returned buffer with its native allocator, not with
 * the CRT: free it with FreeArrayData(), not free() and not FreeString().
 *
 * @param str     Receives the UTF-8 string.
 * @param strLen  Receives the byte length including the null terminator.
 */
void GetMPMInfo(char** str, int32_t* strLen);
#endif /* SANTEC_INCLUDE_MPM */

#ifdef SANTEC_INCLUDE_PCU
/* -------------------------------------------------------------------------
 * PCU control
 * ------------------------------------------------------------------------- */

/**
 * Sets the polarization state on the first available PCU110.
 *
 * @param sop  Polarization state.
 */
void SetPCUSOP(PolarizationState sop);

/**
 * Reads the PCU power monitor.
 *
 * @return  Power reading, or NaN if the PCU is not found.
 */
double ReadPCUPowerMonitor(void);
#endif /* SANTEC_INCLUDE_PCU */

#ifdef SANTEC_INCLUDE_OPM
/* -------------------------------------------------------------------------
 * OPM control
 * ------------------------------------------------------------------------- */

/**
 * Sets the active channel on an OPM-150.
 *
 * @param serialNumberPtr  Serial number (null-terminated).
 * @param channel          Zero-based channel index.
 */
void SetOPMChannel(const char* serialNumberPtr, uint8_t channel);

/**
 * Reads the power from an OPM-150.
 *
 * @param serialNumberPtr  Serial number (null-terminated).
 * @return                 Power value, or NaN if not found.
 */
double ReadOPMPower(const char* serialNumberPtr);

/**
 * Reads power from all channels of an OPM-150.
 *
 * The library allocates the returned array. Free it with FreeAllChannelsRead().
 *
 * @param serialNumberPtr  Serial number (null-terminated).
 * @param data             Receives the power array (NULL on failure).
 * @param length           Receives the element count (0 on failure).
 */
void ReadOPMAllChannels(const char* serialNumberPtr, double** data, int32_t* length);

/**
 * Frees memory allocated by ReadOPMAllChannels().
 *
 * @param data  Pointer to free. NULL is safe.
 */
void FreeAllChannelsRead(double* data);

/**
 * Samples per channel in a bulk power read.
 */
#define OPM_BULK_SAMPLES_PER_CHANNEL 50

/**
 * Maximum number of channels a bulk power read reports.
 */
#define OPM_BULK_MAX_CHANNELS 24

/**
 * Bulk-reads the power samples of every channel of an OPM-150.
 *
 * The device captures OPM_BULK_SAMPLES_PER_CHANNEL samples of each channel and
 * converts them to dBm. Values are channel-major:
 *
 *     data[channelIndex * OPM_BULK_SAMPLES_PER_CHANNEL + sampleIndex]
 *
 * Bulk read requires a USB (FTDI) connection and an averaging level of 4, and is
 * unavailable over the OP-ETH module. A sample is NaN when it could not be read:
 * the connection is not USB, the active wavelength is unknown, or the sample was
 * out of range.
 *
 * The library allocates the buffer. Free it with FreeOPMBulkPowers().
 *
 * @param serialNumberPtr  Serial number (null-terminated).
 * @param data             Receives the power samples in dBm (NULL on failure).
 * @param length           Receives the number of doubles, that is
 *                         channelCount * OPM_BULK_SAMPLES_PER_CHANNEL
 *                         (0 on failure).
 * @param channelCount     Receives the number of channels the buffer holds,
 *                         at most OPM_BULK_MAX_CHANNELS (0 on failure).
 */
void ReadOPMBulkPowers(const char* serialNumberPtr, double** data, int32_t* length, uint8_t* channelCount);

/**
 * Frees memory allocated by ReadOPMBulkPowers().
 *
 * @param data  Pointer to free. NULL is safe.
 */
void FreeOPMBulkPowers(double* data);

/**
 * Sets the OP-ETH session timeout on an OPM-150.
 *
 * Ethernet only; ignored over USB (FTDI).
 *
 * @param serialNumberPtr  Serial number (null-terminated).
 * @param seconds          Timeout in seconds.
 */
void SetOPMTimeout(const char* serialNumberPtr, uint16_t seconds);

/**
 * Sets the averaging level for all channels on an OPM-150.
 *
 * Requires special firmware. Only works over USB (FTDI); the command is
 * not sent over Ethernet.
 *
 * @param serialNumberPtr  Serial number (null-terminated).
 * @param averaging        Averaging level (0 to 4, where 4 is fastest).
 */
void SetOPMAveraging(const char* serialNumberPtr, uint8_t averaging);

/**
 * Gets the averaging level from an OPM-150.
 *
 * Returns the value last passed to SetOPMAveraging().
 * Over Ethernet this cached value may differ from the device's actual
 * setting, since the set command is USB-only.
 *
 * @param serialNumberPtr  Serial number (null-terminated).
 * @return                 Averaging level (0 to 4, where 4 is fastest),
 *                         or 0xFF if the device is not found.
 */
uint8_t GetOPMAveraging(const char* serialNumberPtr);

/**
 * Enables or disables read validation on an OPM-150.
 *
 * When enabled, the device reads all channels three times per call
 * and validates the readings against the threshold from
 * SetOPMReadMaxDeltaDb().
 *
 * @param serialNumberPtr  Serial number (null-terminated).
 * @param enable           Non-zero to enable, zero to disable. A single byte,
 *                         matching the managed entry point.
 */
void SetOPMReadValidation(const char* serialNumberPtr, uint8_t enable);

/**
 * Gets the read validation setting from an OPM-150.
 *
 * @param serialNumberPtr  Serial number (null-terminated).
 * @return                 1 if enabled, 0 if disabled, -1 if not found.
 */
int32_t GetOPMReadValidation(const char* serialNumberPtr);

/**
 * Sets the read validation max delta threshold on an OPM-150.
 *
 * When a channel reading differs from the other two by more than
 * this value (in dB), the device logs a warning during read
 * validation. Default is 0.5 dB. Must be greater than zero.
 *
 * @param serialNumberPtr  Serial number (null-terminated).
 * @param maxDeltaDb       Threshold in dB.
 */
void SetOPMReadMaxDeltaDb(const char* serialNumberPtr, double maxDeltaDb);

/**
 * Gets the read validation maximum delta threshold from an OPM-150.
 *
 * @param serialNumberPtr  Serial number (null-terminated).
 * @return                 Maximum delta threshold (dB),
 *                         or NaN if the device is not found.
 */
double GetOPMReadMaxDeltaDb(const char* serialNumberPtr);

/**
 * Range mode for OPM-150.
 */
#define SANTEC_OPM_RANGE_MODE_MEMBERS \
    OPMRangeMode_RangeHold = 0, \
    OPMRangeMode_AutoRange = 1

#ifdef __cplusplus
typedef enum OPMRangeMode : uint8_t
{
    SANTEC_OPM_RANGE_MODE_MEMBERS
} OPMRangeMode;
#else
typedef uint8_t OPMRangeMode;
enum
{
    SANTEC_OPM_RANGE_MODE_MEMBERS
};
#endif
#undef SANTEC_OPM_RANGE_MODE_MEMBERS

/**
 * Gain level for OPM-150.
 */
#define SANTEC_OPM_GAIN_MEMBERS \
    OPMGain_Gain0   = 0, \
    OPMGain_Gain1   = 1, \
    OPMGain_Gain2   = 2, \
    OPMGain_Gain3   = 3, \
    OPMGain_Gain4   = 4, \
    OPMGain_Gain5   = 5, \
    OPMGain_Gain6   = 6, \
    OPMGain_Gain7   = 7

#ifdef __cplusplus
typedef enum OPMGain : uint8_t
{
    SANTEC_OPM_GAIN_MEMBERS
} OPMGain;
#else
typedef uint8_t OPMGain;
enum
{
    SANTEC_OPM_GAIN_MEMBERS
};
#endif
#undef SANTEC_OPM_GAIN_MEMBERS

/**
 * Sets the range mode on an OPM-150.
 *
 * @param serialNumberPtr  Serial number (null-terminated).
 * @param rangeMode        Range mode to apply.
 */
void SetOPMRangeMode(const char* serialNumberPtr, OPMRangeMode rangeMode);

/**
 * Sets the gain level on an OPM-150.
 *
 * @param serialNumberPtr  Serial number (null-terminated).
 * @param gain             Gain level to apply.
 */
void SetOPMGain(const char* serialNumberPtr, OPMGain gain);

/**
 * Writes staged TCP port, UDP port, and timeout changes to flash.
 *
 * Ethernet only. Does nothing over USB.
 *
 * @param serialNumberPtr  Serial number (null-terminated).
 */
void SaveOPMConfig(const char* serialNumberPtr);

/**
 * Sets the OP-ETH module incoming TCP port on an OPM-150.
 *
 * The change is staged in memory. Call SaveOPMConfig() to write it to flash.
 * Ethernet only. Does nothing over USB.
 *
 * @param serialNumberPtr  Serial number (null-terminated).
 * @param port             TCP port number.
 */
void SetOPMTcpPort(const char* serialNumberPtr, uint16_t port);

/**
 * Sets the OP-ETH module incoming UDP port on an OPM-150.
 *
 * The change is staged in memory. Call SaveOPMConfig() to write it to flash.
 * Ethernet only. Does nothing over USB.
 *
 * @param serialNumberPtr  Serial number (null-terminated).
 * @param port             UDP port number.
 */
void SetOPMUdpPort(const char* serialNumberPtr, uint16_t port);

/**
 * Resets the OP-ETH module port configuration to defaults
 * (TCP=23, UDP=61022, Timeout=60).
 *
 * The reset is staged in memory. Call SaveOPMConfig() to write it to flash.
 * Ethernet only. Does nothing over USB.
 *
 * @param serialNumberPtr  Serial number (null-terminated).
 */
void ResetOPMToDefaultConfig(const char* serialNumberPtr);

/**
 * Reads the staged OP-ETH module port and timeout configuration.
 *
 * Returns the values last set by SetOPMTcpPort(), SetOPMUdpPort(), or
 * SetOPMTimeout(). When nothing has been staged, the flash values are
 * returned instead. Works over TCP or UDP. Does nothing over USB.
 *
 * @param serialNumberPtr  Serial number (null-terminated).
 * @param tcpPort          Receives the staged TCP port.
 * @param udpPort          Receives the staged UDP port.
 * @param timeout          Receives the staged timeout in seconds.
 */
void GetOPMTempConfig(const char* serialNumberPtr,
                      uint16_t* tcpPort, uint16_t* udpPort, uint16_t* timeout);

/**
 * Reads the OP-ETH module port and timeout configuration from flash.
 *
 * Works over TCP or UDP. Does nothing over USB.
 *
 * @param serialNumberPtr  Serial number (null-terminated).
 * @param tcpPort          Receives the saved TCP port.
 * @param udpPort          Receives the saved UDP port.
 * @param timeout          Receives the saved timeout in seconds.
 */
void GetOPMFlashConfig(const char* serialNumberPtr,
                       uint16_t* tcpPort, uint16_t* udpPort, uint16_t* timeout);
#endif /* SANTEC_INCLUDE_OPM */

#if defined(SANTEC_INCLUDE_TSL) || defined(SANTEC_INCLUDE_OPM)
/**
 * Sets the wavelength on the TSL and all connected OPM-150 devices.
 *
 * @param wavelength  Nominal wavelength band.
 */
void SetWavelength(NominalWavelength wavelength);
#endif /* SANTEC_INCLUDE_TSL || SANTEC_INCLUDE_OPM */

#ifdef SANTEC_INCLUDE_OPM_NETWORK
/* -------------------------------------------------------------------------
 * OPM network configuration
 * ------------------------------------------------------------------------- */

/**
 * Discovers OPM-150 devices on the network via GIPA broadcast.
 *
 * The library allocates the returned string. Free it with FreeString().
 *
 * @return  Discovery responses (one per line, UTF-8), or NULL if none respond.
 */
char* DiscoverOPMDevices(void);

/**
 * Sets the IP address and netmask of an OPM-150 via SIPA broadcast.
 *
 * Pass "0.0.0.0" for the IP to enable DHCP.
 * The library allocates the returned string. Free it with FreeString().
 *
 * @param macAddressPtr  MAC address ("00-00-5E-00-53-00").
 * @param ipAddressPtr   IP address, or "0.0.0.0" for DHCP.
 * @param maskPtr        Netmask ("255.255.255.0").
 * @return               Device response (UTF-8), or NULL on error.
 */
char* SetOPMNetworkConfig(const char* macAddressPtr, const char* ipAddressPtr,
                          const char* maskPtr);

/**
 * Queries temporary IP config from all OPM-150 devices via TIPA broadcast.
 *
 * The library allocates the returned string. Free it with FreeString().
 *
 * @return  TIPA responses (one per line, UTF-8), or NULL if none respond.
 */
char* QueryOPMTempConfig(void);

/**
 * Commits the temporary IP configuration to flash via UIPC broadcast.
 *
 * The library allocates the returned string. Free it with FreeString().
 *
 * @param macAddressPtr  MAC address ("00-00-5E-00-53-00").
 * @return               Device response (UTF-8), or NULL on error.
 */
char* ApplyOPMNetworkConfig(const char* macAddressPtr);

/**
 * Clears the cached network interfaces.
 *
 * After calling this, SetOPMNetworkConfig(), QueryOPMTempConfig(), and
 * ApplyOPMNetworkConfig() will require a fresh DiscoverOPMDevices() call.
 */
void ClearDiscoveredOPMNics(void);
#endif /* SANTEC_INCLUDE_OPM_NETWORK */

#ifdef SANTEC_INCLUDE_PDL_CALCULATION
/* -------------------------------------------------------------------------
 * PDL / IL calculation
 * ------------------------------------------------------------------------- */

/**
 * Power readings for four polarization states.
 *
 * Mirrors the C# PowerData inline array (4 x double).
 */
typedef struct PowerData
{
    double Power[4];
} PowerData;

/**
 * Calculates insertion loss and polarization-dependent loss.
 *
 * Uses the four-SOP Jones-matrix method (LHP, LVP, LP45, LCP) via the
 * connected PCU110.
 *
 * @param nominalWavelength             Nominal wavelength band.
 * @param referenceData                 Reference scan power readings.
 * @param measurementData               Measurement scan power readings.
 * @param referencePowerMonitorData     Reference scan monitor readings.
 * @param measurementPowerMonitorData   Measurement scan monitor readings.
 * @param il                            Receives the insertion loss (dB).
 * @param pdl                           Receives the polarization-dependent loss (dB).
 */
void Calculation(
    NominalWavelength nominalWavelength,
    PowerData      referenceData,
    PowerData      measurementData,
    PowerData      referencePowerMonitorData,
    PowerData      measurementPowerMonitorData,
    double*        il,
    double*        pdl);
#endif /* SANTEC_INCLUDE_PDL_CALCULATION */

/* -------------------------------------------------------------------------
 * Native memory management
 * ------------------------------------------------------------------------- */

/**
 * Frees memory allocated by array-returning functions.
 *
 * @param data  Pointer to free. NULL is safe.
 */
void FreeArrayData(void* data);

/**
 * Frees a string returned by the library.
 *
 * Covers DiscoverOPMDevices, SetOPMNetworkConfig, QueryOPMTempConfig,
 * ApplyOPMNetworkConfig, ValidateParameters and GetLibraryVersion.
 *
 * @param str  Pointer to free. NULL is safe.
 */
void FreeString(void* str);

/**
 * Returns the library version as a UTF-8 string.
 *
 * Lets a caller identify the binary it loaded without reading the file's
 * version resource. Free the result with FreeString().
 *
 * @return  Version string, or NULL if it could not be produced.
 */
char* GetLibraryVersion(void);

#ifdef __cplusplus
}
#endif

#endif /* SANTEC_LIBRARY_H */
