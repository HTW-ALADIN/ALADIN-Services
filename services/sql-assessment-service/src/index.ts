import dotenv from 'dotenv';
dotenv.config();

import { createControllers } from './bootstrap';
import { registerControllers, startRestApi } from './api/rest-api';

const {
	connectionController,
	taskGenerationController,
	gradingController,
	descriptionController,
	queryExecutionController,
} = createControllers();

registerControllers(
	connectionController,
	taskGenerationController,
	gradingController,
	descriptionController,
	queryExecutionController,
);
startRestApi();
