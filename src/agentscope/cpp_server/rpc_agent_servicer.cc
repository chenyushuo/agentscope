#include <csignal>
#include <iostream>
#include <string>
#include <utility>

#include <grpc/grpc.h>
#include <grpcpp/security/server_credentials.h>
#include <grpcpp/server.h>
#include <grpcpp/server_builder.h>
#include <grpcpp/server_context.h>
#include <pybind11/pybind11.h>

#include "rpc_agent.grpc.pb.h"
#include "worker.h"

using std::pair;
using std::string;

using grpc::Server;
using grpc::ServerBuilder;
using grpc::ServerContext;
using grpc::ServerReader;
using grpc::ServerReaderWriter;
using grpc::ServerWriter;
using grpc::Status;

using google::protobuf::Empty;

Worker *worker = nullptr;

#define LOG(...) RAW_LOGGER(worker, __VA_ARGS__)

class RpcAgentServiceImpl final : public RpcAgent::Service {
private:
  Worker *_worker;

public:
  RpcAgentServiceImpl(Worker *worker) : _worker(worker) {}

  ~RpcAgentServiceImpl() {}

  // check server is alive
  Status is_alive(ServerContext *context, const Empty *request,
                  GeneralResponse *response) override {
    response->set_ok(true);
    return Status::OK;
  }

  // stop the server
  Status stop(ServerContext *context, const Empty *request,
              GeneralResponse *response) override {
    response->set_ok(true);
    return Status::OK;
  }

  // create a new agent on the server
  Status create_agent(ServerContext *context, const CreateAgentRequest *request,
                      GeneralResponse *response) override {
    const string &agent_id = request->agent_id();
    const string &agent_init_args = request->agent_init_args();
    const string &agent_source_code = request->agent_source_code();
    const string &result = _worker->call_create_agent(agent_id, agent_init_args,
                                                      agent_source_code);
    response->set_ok(result.empty());
    response->set_message(result);
    return Status::OK;
  }
  // delete agent from the server
  Status delete_agent(ServerContext *context, const StringMsg *request,
                      GeneralResponse *response) override {
    string agent_id = request->value();
    const string &result = _worker->call_delete_agent(agent_id);
    response->set_ok(result.size() == 0);
    response->set_message(result);
    return Status::OK;
  }

  // clear all agent on the server
  Status delete_all_agents(ServerContext *context, const Empty *request,
                           GeneralResponse *response) override {
    const string &result = _worker->call_delete_all_agents();
    response->set_ok(result.size() == 0);
    response->set_message(result);
    return Status::OK;
  }

  // clone an agent with specific agent_id
  Status clone_agent(ServerContext *context, const StringMsg *request,
                     GeneralResponse *response) override {
    string agent_id = request->value();
    auto [is_ok, result] = _worker->call_clone_agent(agent_id);
    response->set_ok(is_ok);
    response->set_message(result);
    return Status::OK;
  }

  // get id of all agents on the server as a list
  Status get_agent_list(ServerContext *context, const Empty *request,
                        GeneralResponse *response) override {
    const string &result = _worker->call_get_agent_list();
    response->set_ok(true);
    response->set_message(result);
    return Status::OK;
  }

  // get the resource utilization information of the server
  Status get_server_info(ServerContext *context, const Empty *request,
                         GeneralResponse *response) override {
    const string &result = _worker->call_server_info();
    response->set_ok(true);
    response->set_message(result);
    return Status::OK;
  }

  // update the model configs in the server
  Status set_model_configs(ServerContext *context, const StringMsg *request,
                           GeneralResponse *response) override {
    const string &model_configs = request->value();
    const string &result = _worker->call_set_model_configs(model_configs);
    response->set_ok(result.size() == 0);
    response->set_message(result);
    return Status::OK;
  }

  // get memory of a specific agent
  Status get_agent_memory(ServerContext *context, const StringMsg *request,
                          GeneralResponse *response) override {
    string agent_id = request->value();
    auto [is_ok, result] = _worker->call_get_agent_memory(agent_id);
    response->set_ok(is_ok);
    response->set_message(result);
    return Status::OK;
  }

  // call funcs of agent running on the server
  Status call_agent_func(ServerContext *context, const CallFuncRequest *request,
                         CallFuncResponse *response) override {
    auto agent_id = request->agent_id();
    auto func_name = request->target_func();
    auto raw_value = request->value();
    pair<bool, string> result = _worker->call_agent_func(agent_id, func_name, raw_value);
    if (result.first) {
      response->set_ok(true);
      response->set_value(result.second);
    } else {
      return Status(grpc::StatusCode::INVALID_ARGUMENT, result.second);
    }
    return Status::OK;
  }

  // update value of PlaceholderMessage
  Status update_placeholder(ServerContext *context,
                            const UpdatePlaceholderRequest *request,
                            CallFuncResponse *response) override {
    auto task_id = request->task_id();
    auto [is_ok, result] = _worker->call_update_placeholder(task_id);
    response->set_ok(is_ok);
    response->set_value(result);
    LOG(FORMAT(task_id), FORMAT(is_ok), FORMAT(result.size()), BIN_FORMAT(result));
    return Status::OK;
  }

  // file transfer
  Status download_file(ServerContext *context, const StringMsg *request,
                       ServerWriter<ByteMsg> *writer) override {
    std::string filepath = request->value();
    LOG(FORMAT(filepath));
    if (!std::filesystem::exists(filepath)) {
      return Status(grpc::StatusCode::NOT_FOUND,
                    string("File ") + filepath + " not found");
    }

    std::ifstream file(filepath, std::ios::binary);
    if (!file.is_open()) {
      return Status(grpc::StatusCode::NOT_FOUND, "Failed to open the file");
    }

    auto buffer = std::make_unique<char[]>(1024 * 1024);
    auto read_size = sizeof(char) * 1024 * 1024;
    while (true) {
      file.read(buffer.get(), read_size);
      if (!file && !file.eof()) {
        file.close();
        return Status(grpc::StatusCode::INTERNAL,
                      "Error occurred while reading the file");
      }
      ByteMsg piece;
      string data = std::string(buffer.get(), file.gcount());
      piece.set_data(data);
      if (!writer->Write(piece)) {
        file.close();
        return Status(grpc::StatusCode::ABORTED,
                      "Failed to send data to client");
      }
      if (file.eof()) {
        file.close();
        return Status::OK;
      }
    }
  }
};

std::unique_ptr<Server> server = nullptr;
std::shared_ptr<RpcAgentServiceImpl> service = nullptr;
ServerBuilder builder;

void RunServer(const string &server_address) {
  service = std::make_shared<RpcAgentServiceImpl>(worker);
  builder.AddListeningPort(server_address, grpc::InsecureServerCredentials());
  builder.RegisterService(service.get());
  server = builder.BuildAndStart();
  auto server_thread = std::thread([&]() { server->Wait(); });
  server_thread.detach();
}

void ShutdownCppServer();
void signal_handler(int signum) {
  if (worker != nullptr) {
    ShutdownCppServer();
  }
  exit(0);
}

void SetupCppServer(const string &host, const string &port,
                    const string &server_id, const string &studio_url,
                    const string &pool_type, const string &redis_url,
                    const int max_pool_size,
                    const int max_expire_time, const int max_timeout_seconds,
                    const bool local_mode,  const int num_workers) {
  struct sigaction act;
  act.sa_handler = signal_handler;
  sigemptyset(&act.sa_mask);
  act.sa_flags = 0;
  sigaction(SIGINT, &act, NULL);
  std::string server_address;
  if (local_mode)
  {
    server_address = "localhost:" + port;
  }
  else {
    server_address = "0.0.0.0:" + port;
  }
  worker = new Worker(host, port, server_id, studio_url,
                      pool_type, redis_url, max_pool_size,
                      max_expire_time, max_timeout_seconds, num_workers);
  RunServer(server_address);
}


void ShutdownCppServer() {
  server->Shutdown();
  delete worker;
}

PYBIND11_MODULE(cpp_server, m) {
  m.doc() = "cpp_server module";
  m.def("setup_cpp_server", &SetupCppServer, "Run the gRPC server",
        py::arg("host"), py::arg("port"), py::arg("server_id"), py::arg("studio_url"),
        py::arg("pool_type"), py::arg("redis_url"),
        py::arg("max_pool_size"), py::arg("max_expire_time"), py::arg("max_timeout_seconds"),
        py::arg("local_mode"), py::arg("num_workers"));
  m.def("shutdown_cpp_server", &ShutdownCppServer, "Shutdown the gRPC server");
}
