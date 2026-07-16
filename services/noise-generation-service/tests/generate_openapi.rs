use noise_generation_service::ApiDoc;
use utoipa::OpenApi;

#[test]
fn generate_openapi() {
    let openapi = noise_generation_service::ApiDoc::openapi();
    let json = openapi.to_pretty_json().unwrap();
    std::fs::write("noise-generation-service.openapi.json", json).unwrap();
}
