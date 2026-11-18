{{/*
Chart name.
*/}}
{{- define "bigid-assignment.name" -}}
{{- .Chart.Name | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Full name: <release>-<chart>, or just <release> if it already contains the chart name.
Truncated to 63 chars (DNS name limit).
*/}}
{{- define "bigid-assignment.fullname" -}}
{{- if contains .Chart.Name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name .Chart.Name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}

{{/*
Chart label: <name>-<version>.
*/}}
{{- define "bigid-assignment.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels.
*/}}
{{- define "bigid-assignment.labels" -}}
helm.sh/chart: {{ include "bigid-assignment.chart" . }}
{{ include "bigid-assignment.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels (must never change after install).
*/}}
{{- define "bigid-assignment.selectorLabels" -}}
app.kubernetes.io/name: {{ include "bigid-assignment.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}
