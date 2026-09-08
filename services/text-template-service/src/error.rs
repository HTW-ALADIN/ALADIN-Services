use axum::{
    http::{header, StatusCode},
    response::{IntoResponse, Response},
    Json,
};
use serde::Serialize;
use utoipa::ToSchema;

#[derive(Debug, Clone, Serialize, ToSchema)]
pub struct ProblemDetails {
    #[serde(rename = "type")]
    pub problem_type: String,
    pub title: String,
    pub status: u16,
    pub detail: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub template: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub line: Option<usize>,
}

#[derive(Debug, Clone)]
pub struct ServiceError {
    pub code: &'static str,
    pub status: StatusCode,
    pub title: &'static str,
    pub detail: String,
    pub template: Option<String>,
    pub line: Option<usize>,
}

impl ServiceError {
    pub fn invalid(detail: impl Into<String>) -> Self {
        Self::new(
            "invalid-request",
            StatusCode::BAD_REQUEST,
            "Invalid request",
            detail,
        )
    }

    pub fn resource_limit(detail: impl Into<String>) -> Self {
        Self::new(
            "resource-limit",
            StatusCode::UNPROCESSABLE_ENTITY,
            "Resource limit exceeded",
            detail,
        )
    }

    pub fn payload_too_large(detail: impl Into<String>) -> Self {
        Self::new(
            "resource-limit",
            StatusCode::PAYLOAD_TOO_LARGE,
            "Payload too large",
            detail,
        )
    }

    pub fn not_acceptable(detail: impl Into<String>) -> Self {
        Self::new(
            "not-acceptable",
            StatusCode::NOT_ACCEPTABLE,
            "Unsupported response media type",
            detail,
        )
    }

    pub fn unavailable(detail: impl Into<String>) -> Self {
        Self::new(
            "render-capacity-exhausted",
            StatusCode::SERVICE_UNAVAILABLE,
            "Render capacity exhausted",
            detail,
        )
    }

    pub fn internal(detail: impl Into<String>) -> Self {
        Self::new(
            "internal-error",
            StatusCode::INTERNAL_SERVER_ERROR,
            "Internal server error",
            detail,
        )
    }

    pub fn new(
        code: &'static str,
        status: StatusCode,
        title: &'static str,
        detail: impl Into<String>,
    ) -> Self {
        Self {
            code,
            status,
            title,
            detail: detail.into(),
            template: None,
            line: None,
        }
    }

    pub fn with_location(mut self, template: Option<&str>, line: Option<usize>) -> Self {
        self.template = template.map(ToOwned::to_owned);
        self.line = line;
        self
    }

    pub fn problem(&self) -> ProblemDetails {
        ProblemDetails {
            problem_type: format!("urn:problem:text-template:{}", self.code),
            title: self.title.to_string(),
            status: self.status.as_u16(),
            detail: self.detail.clone(),
            template: self.template.clone(),
            line: self.line,
        }
    }
}

impl std::fmt::Display for ServiceError {
    fn fmt(&self, formatter: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(formatter, "{}: {}", self.title, self.detail)
    }
}

impl std::error::Error for ServiceError {}

impl IntoResponse for ServiceError {
    fn into_response(self) -> Response {
        let mut response = (self.status, Json(self.problem())).into_response();
        response.headers_mut().insert(
            header::CONTENT_TYPE,
            header::HeaderValue::from_static("application/problem+json"),
        );
        response
    }
}

#[cfg(test)]
mod tests {
    use super::ServiceError;

    #[test]
    fn internal_errors_have_a_stable_display_contract() {
        let error = ServiceError::internal("private failure");

        assert_eq!(error.code, "internal-error");
        assert_eq!(error.to_string(), "Internal server error: private failure");
    }
}
