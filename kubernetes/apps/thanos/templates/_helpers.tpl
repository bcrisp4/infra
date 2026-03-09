{{- define "thanos.name" -}}
{{- .Chart.Name | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "thanos.fullname" -}}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "thanos.image" -}}
{{ .Values.image.repository }}:{{ .Values.image.tag | default (printf "v%s" .Chart.AppVersion) }}
{{- end }}

{{- define "thanos.labels" -}}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
helm.sh/chart: {{ printf "%s-%s" .Chart.Name .Chart.Version }}
{{- end }}

{{- define "thanos.selectorLabels" -}}
app.kubernetes.io/name: {{ include "thanos.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}
