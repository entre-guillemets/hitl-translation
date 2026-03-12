from fastapi import HTTPException, Request


def get_fuzzy_matcher(request: Request):
    matcher = getattr(request.app.state, "fuzzy_matcher", None)
    if matcher is None:
        raise HTTPException(status_code=503, detail="Fuzzy matching service not initialized.")
    return matcher


def get_multi_engine_service(request: Request):
    service = getattr(request.app.state, "multi_engine_service", None)
    if service is None:
        raise HTTPException(status_code=503, detail="Multi-engine service not initialized.")
    return service


def get_multimodal_service(request: Request):
    service = getattr(request.app.state, "multimodal_service", None)
    if service is None:
        raise HTTPException(status_code=503, detail="Multimodal service not initialized.")
    return service


def get_comet_model(request: Request):
    # May be None if COMET failed to load; callers must check
    return getattr(request.app.state, "comet_model", None)


def get_metricx_service(request: Request):
    # May be None; callers must check
    return getattr(request.app.state, "metricx_service", None)


def get_health_service(request: Request):
    service = getattr(request.app.state, "health_service", None)
    if service is None:
        raise HTTPException(status_code=503, detail="Health service not initialized.")
    return service


def get_transcreation_service(request: Request):
    service = getattr(request.app.state, "transcreation_service", None)
    if service is None:
        raise HTTPException(status_code=503, detail="Transcreation service not initialized.")
    return service
