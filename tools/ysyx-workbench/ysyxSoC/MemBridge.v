module MemBridge(
  input         clock,
  input         reset,
  input  [31:0] io_ifu_addr,
  input         io_ifu_reqValid,
  output [31:0] io_ifu_rdata,
  output        io_ifu_respValid,
  input  [31:0] io_lsu_addr,
  input         io_lsu_reqValid,
  output [31:0] io_lsu_rdata,
  output        io_lsu_respValid,
  input  [1:0]  io_lsu_size,
  input         io_lsu_wen,
  input  [31:0] io_lsu_wdata,
  input  [3:0]  io_lsu_wmask,
  input         io_out_awready,
  output        io_out_awvalid,
  output [3:0]  io_out_awid,
  output [31:0] io_out_awaddr,
  output [7:0]  io_out_awlen,
  output [2:0]  io_out_awsize,
  output [1:0]  io_out_awburst,
  input         io_out_wready,
  output        io_out_wvalid,
  output [31:0] io_out_wdata,
  output [3:0]  io_out_wstrb,
  output        io_out_wlast,
  output        io_out_bready,
  input         io_out_bvalid,
  input  [3:0]  io_out_bid,
  input  [1:0]  io_out_bresp,
  input         io_out_arready,
  output        io_out_arvalid,
  output [3:0]  io_out_arid,
  output [31:0] io_out_araddr,
  output [7:0]  io_out_arlen,
  output [2:0]  io_out_arsize,
  output [1:0]  io_out_arburst,
  output        io_out_rready,
  input         io_out_rvalid,
  input  [3:0]  io_out_rid,
  input  [31:0] io_out_rdata,
  input  [1:0]  io_out_rresp,
  input         io_out_rlast
);

  wire        isValidLoad = io_lsu_reqValid & ~io_lsu_wen;
  wire        isValidStore = io_lsu_reqValid & io_lsu_wen;
  reg  [1:0]  stateI;
  wire        _io_out_arvalid_T = stateI == 2'h0;
  wire        _io_out_arvalid_T_2 = stateI == 2'h1;
  wire        _instReturn_T = stateI == 2'h2;
  reg  [2:0]  stateD;
  wire        _io_out_wvalid_T = stateD == 3'h0;
  wire        _lsuRead_T_2 = stateD == 3'h1;
  wire        _io_lsu_respValid_T = stateD == 3'h2;
  wire        _io_out_awvalid_T_2 = stateD == 3'h3;
  wire        _io_out_awvalid_T_3 = stateD == 3'h5;
  wire        _io_out_wvalid_T_2 = stateD == 3'h4;
  wire        io_out_bready_0 = stateD == 3'h6;
  wire        lsuRead = _io_out_wvalid_T & isValidLoad | _lsuRead_T_2;
  wire        instReturn = io_out_rvalid & _instReturn_T;
  reg  [31:0] io_ifu_rdata_r;
  always @(posedge clock) begin
    if (reset) begin
      stateI <= 2'h0;
      stateD <= 3'h0;
    end
    else begin
      automatic logic [1:0] _stateD_T_22 = io_out_arready ? 2'h2 : 2'h1;
      automatic logic [1:0] _stateD_T_24 = {~io_out_rvalid, 1'h0};
      automatic logic [2:0] _stateD_T_30 = {1'h1, io_out_wready, 1'h0};
      automatic logic [2:0] _stateD_T_21 =
        _io_out_wvalid_T
          ? (isValidLoad
               ? {1'h0, _stateD_T_22}
               : isValidStore
                   ? (io_out_awready ? _stateD_T_30 : io_out_wready ? 3'h5 : 3'h3)
                   : 3'h0)
          : 3'h0;
      stateI <=
        (_io_out_arvalid_T & io_ifu_reqValid | _io_out_arvalid_T_2
           ? _stateD_T_22
           : 2'h0) | (_instReturn_T ? _stateD_T_24 : 2'h0);
      stateD <=
        {_stateD_T_21[2],
         _stateD_T_21[1:0] | (_lsuRead_T_2 ? _stateD_T_22 : 2'h0)
           | (_io_lsu_respValid_T ? _stateD_T_24 : 2'h0)}
        | (_io_out_awvalid_T_2 ? (io_out_awready ? _stateD_T_30 : 3'h3) : 3'h0)
        | (_io_out_awvalid_T_3 ? (io_out_awready ? 3'h6 : 3'h5) : 3'h0)
        | (_io_out_wvalid_T_2 ? _stateD_T_30 : 3'h0)
        | (~io_out_bready_0 | io_out_bvalid ? 3'h0 : 3'h6);
    end
    if (instReturn)
      io_ifu_rdata_r <= io_out_rdata;
  end // always @(posedge)
  `ifdef ENABLE_INITIAL_REG_
    `ifdef FIRRTL_BEFORE_INITIAL
      `FIRRTL_BEFORE_INITIAL
    `endif // FIRRTL_BEFORE_INITIAL
    initial begin
      automatic logic [31:0] _RANDOM[0:1];
      `ifdef INIT_RANDOM_PROLOG_
        `INIT_RANDOM_PROLOG_
      `endif // INIT_RANDOM_PROLOG_
      `ifdef RANDOMIZE_REG_INIT
        for (logic [1:0] i = 2'h0; i < 2'h2; i += 2'h1) begin
          _RANDOM[i[0]] = `RANDOM;
        end
        stateI = _RANDOM[1'h0][1:0];
        stateD = _RANDOM[1'h0][4:2];
        io_ifu_rdata_r = {_RANDOM[1'h0][31:5], _RANDOM[1'h1][4:0]};
      `endif // RANDOMIZE_REG_INIT
    end // initial
    `ifdef FIRRTL_AFTER_INITIAL
      `FIRRTL_AFTER_INITIAL
    `endif // FIRRTL_AFTER_INITIAL
  `endif // ENABLE_INITIAL_REG_
  assign io_ifu_rdata = instReturn ? io_out_rdata : io_ifu_rdata_r;
  assign io_ifu_respValid = instReturn;
  assign io_lsu_rdata = io_out_rdata;
  assign io_lsu_respValid =
    _io_lsu_respValid_T & io_out_rvalid | io_out_bready_0 & io_out_bvalid;
  assign io_out_awvalid =
    |{_io_out_wvalid_T & isValidStore, _io_out_awvalid_T_3, _io_out_awvalid_T_2};
  assign io_out_awid = 4'h0;
  assign io_out_awaddr = io_lsu_addr;
  assign io_out_awlen = 8'h0;
  assign io_out_awsize = {1'h0, io_lsu_size};
  assign io_out_awburst = 2'h0;
  assign io_out_wvalid = _io_out_wvalid_T & isValidStore | _io_out_wvalid_T_2;
  assign io_out_wdata = io_lsu_wdata;
  assign io_out_wstrb = io_lsu_wmask;
  assign io_out_wlast = 1'h1;
  assign io_out_bready = io_out_bready_0;
  assign io_out_arvalid =
    _io_out_arvalid_T & io_ifu_reqValid | _io_out_arvalid_T_2 | lsuRead;
  assign io_out_arid = 4'h0;
  assign io_out_araddr = lsuRead ? io_lsu_addr : io_ifu_addr;
  assign io_out_arlen = 8'h0;
  assign io_out_arsize = {1'h0, lsuRead ? io_lsu_size : 2'h2};
  assign io_out_arburst = 2'h0;
  assign io_out_rready = _instReturn_T | _io_lsu_respValid_T;
endmodule
